# 패키지 임포트
from collections import deque
from imutils.video import VideoStream
import numpy as np
import argparse
import cv2
import imutils
import time
import threading
import socket

print("########### Pong GPT V10 ############")


##### 중요 환경 변수들 #####
VIDEO_SELECTION = 2  # 0번부터 카메라 포트 찾아서 1씩 올려보기
VIDEO_WIDTH = 1000  # 화면 가로 넓이
WIDTH_CUT = 160
CENTER_LINE = 340  # 세로 센터 라인
NET_LINE = 250  # 네트 라인

CATCH_FRAME = 3 # 좌표 계산 프레임 수
MIN_GAP = 10 # 최소 감지 속도 (px)
MOVE_FIX = 0.4 # 최종 좌표 미세 조정
HIT_LINE = 750 - 100 # 타격 명령 감지 범위 (px)
LINE_DEACTIVE_TIME = 0.8 # 감지 비활성화 시간 (sec)
ACTU_WAIT_TIME = 500 # 엑추에이터 이동 후 대기 시간 (ms)

# 초기화 변수들
line_on = False
hit_on = False
FINAL_MOVE = 0  # 단위 cm

# 주황색 탁구공 HSV 색 범위 지정 (창문쪽 형광등 두 개 키고 문쪽 형광등 한 개 껐을때 기준)
orangeLower = (1, 130, 240)
orangeUpper = (30, 255, 255)

# 파서 코딩 부분
ap = argparse.ArgumentParser()
ap.add_argument("-v", "--video", help="path to the (optional) video file")
ap.add_argument("-b", "--buffer", type=int, default=64, help="max buffer size")
args = vars(ap.parse_args())

# 데큐 생성
pts = deque(maxlen=args["buffer"])
line_xy = deque(maxlen=2)  # 단위 px
temp_move = deque()  # 단위 px


# Line Activater 쓰레드 함수
def line_activator(ETA):
    line_xy.clear()
    temp_move.clear()

    global line_on
    line_on = True
    print("Line Activated / Detecting LOCK")
    time.sleep(ETA)
    global hit_on
    hit_on = False
    line_on = False
    print("Line Deactivated / Detecting UNLOCK")

# 비디오 스트리밍 시작
vs = VideoStream(src=VIDEO_SELECTION).start()
time.sleep(2.0)

# 프레임 단위 무한 루프 영역
while True:
    frame = vs.read()
    frame = frame[1] if args.get("video", False) else frame
    if frame is None:
        break
    # 화면비 (680x750)
    frame = imutils.resize(frame, width=VIDEO_WIDTH)
    frame = frame[0:750, WIDTH_CUT : 1000 - WIDTH_CUT]
    # 영상처리
    blurred = cv2.GaussianBlur(frame, (11, 11), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, orangeLower, orangeUpper)
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)
    cv2.imshow("mask", mask)
    cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = imutils.grab_contours(cnts)
    center = None
    # 감지 했을 경우 (center 좌표 계산됨)
    if len(cnts) > 0:
        c = max(cnts, key=cv2.contourArea)
        ((x, y), radius) = cv2.minEnclosingCircle(c)
        M = cv2.moments(c)
        center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

        # 탁구 알고리즘
        if line_on == False:
            line_xy.append(center)
            if len(line_xy) == 2:
                if line_xy[0][1] + MIN_GAP < line_xy[1][1]:
                    temp_move.append(
                        int(
                            (750 - line_xy[0][1])
                            * (line_xy[0][0] - line_xy[1][0])
                            / (line_xy[0][1] - line_xy[1][1])
                            + line_xy[0][0]
                        )
                    )

                if line_xy[0][1] > line_xy[1][1]:
                    line_xy.clear()


        if len(temp_move) == CATCH_FRAME:
            temp_move.popleft()

            # move 계산
            temp_move_sum = 0
            for i in range(CATCH_FRAME - 1):
                temp_move_sum += temp_move.popleft()
            FINAL_MOVE = int(temp_move_sum / (CATCH_FRAME - 1) * (152.5 / 680))
            if FINAL_MOVE < 76:
                FINAL_MOVE -= int((76 - FINAL_MOVE) * MOVE_FIX)
            else:
                FINAL_MOVE += int((FINAL_MOVE - 76) * MOVE_FIX)

            print(
                "FINAL MOVE : {0}cm".format(
                    FINAL_MOVE
                )
            )


            # 감지 대기 쓰레드
            lineact_tr = threading.Thread(
                target=line_activator, args=(LINE_DEACTIVE_TIME,), daemon=True
            )
            lineact_tr.start()
        
        if center[1] > HIT_LINE and line_on == True and hit_on == False:
            hit_on = True
            print("Hit! : {0}".format(center))
            time.sleep(10)
            
    # rgb 트레킹 레드라인 코드
    pts.appendleft(center)
    for i in range(1, len(pts)):
        if pts[i - 1] is None or pts[i] is None:
            continue
        thickness = int(np.sqrt(args["buffer"] / float(i + 1)) * 2.5)
        cv2.line(frame, pts[i - 1], pts[i], (0, 0, 255), thickness)

    # 화면 표시 선 코드
    # 중앙선
    cv2.line(frame, (CENTER_LINE, 0), (CENTER_LINE, 750), (255, 255, 255), 2)

    # 네트선
    cv2.line(frame, (0, NET_LINE), (VIDEO_WIDTH, NET_LINE), (255, 255, 255), 2)

    # 화면 띄우기
    cv2.imshow("Frame", frame)

    

    # q : 종료 r : 리셋
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    elif key == ord("r"):
        line_xy.clear()
        temp_move.clear()
        line_on = False
        hit_on = False
        FINAL_MOVE = None

if not args.get("video", False):
    vs.stop()
else:
    vs.release()

cv2.destroyAllWindows()
