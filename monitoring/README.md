# Monitoring System

정책/에너지/산업/시장 모니터링 전담 에이전트용 설정과 상태 저장 디렉토리.

## 파일
- `config.json`: 모니터링 대상, 키워드, 분류 설정
- `state.json`: 이전 실행 상태 및 중복 제거용 저장소
- `reports/`: 실행 결과 브리핑 저장
- `scripts/monitor.py`: 1차 수집/선별/브리핑 스크립트

## 실행
```powershell
python monitoring/scripts/monitor.py --limit-per-source 5
python monitoring/scripts/monitor.py --groups "일 1회"
python monitoring/scripts/monitor.py --groups "일 3회,실시간"
```

## 목적
- URL 직접 접근 우선
- 최신순 목록 확인
- 제목/요약/본문/첨부파일명 기준 키워드 매칭
- 신규/변경분 우선 브리핑
- 중복 제거 및 제외 사유 기록
