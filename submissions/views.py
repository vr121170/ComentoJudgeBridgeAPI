import json
import time

from django.shortcuts import render
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class Judge0SubmissionView(APIView):
    # Judge0 API URL
    JUDGE0_URL = "https://579f-112-168-108-61.ngrok-free.app/submissions/"

    def post(self, request):
        source_code = request.data.get("source_code", "")
        language_id = request.data.get("language_id", 1)
        test_case = request.data.get("test_case", "[]")
        cpu_time_limit = request.data.get("cpu_time_limit", "")
        memory_limit = request.data.get("memory_limit", "")

        try:
            # 테스트 케이스 JSON 파싱
            test_case_list = json.loads(test_case)
        except json.JSONDecodeError:
            return Response(
                {"error": "Invalid test_case format. Must be a valid JSON array."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(test_case_list, list):
            return Response(
                {"error": "test_case must be a list of test case objects."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        headers = {
            "Content-Type": "application/json",
        }

        tokens = []  # 반환된 토큰 저장 리스트

        try:
            # Judge0 API로 제출 요청
            for case in test_case_list:
                stdin = case.get("stdin", "")
                expected_output = case.get("expected_output", "")

                payload = {
                    "source_code": source_code,
                    "language_id": language_id,
                    "stdin": stdin,
                    "expected_output": expected_output,
                    "cpu_time_limit": cpu_time_limit,
                    "memory_limit": memory_limit,
                }

                response = requests.post(self.JUDGE0_URL, json=payload, headers=headers)
                if response.status_code == 201:  # 제출 성공
                    tokens.append(response.json().get("token"))
                else:
                    return Response(
                        {
                            "error": "Failed to submit to Judge0",
                            "details": response.json(),
                        },
                        status=response.status_code,
                    )

            # 각 토큰 결과 조회
            results = []
            memory_usages = []
            execution_times = []
            all_success = True

            for token in tokens:
                result = self.get_result_with_retry(token, headers)
                if result is not None:
                    success = result.get("status", {}).get("description") == "Accepted"
                    memory = result.get("memory", 0) or 0
                    time = result.get("time", 0) or 0

                    memory_usages.append(memory)
                    execution_times.append(time)

                    all_success = all_success and success

                    results.append({
                        "token": token,
                        "status": result.get("status", {}).get("description"),
                        "time": time,
                        "memory": memory,
                    })
                else:
                    results.append({
                        "token": token,
                        "status": "Timeout",
                        "time": 0,
                        "memory": 0,
                    })
                    all_success = False

            # 최대 메모리와 최대 실행 시간 계산
            max_memory = max(memory_usages) if memory_usages else 0
            max_time = max(execution_times) if execution_times else 0

            # 최종 결과 반환
            return Response({
                "all_success": all_success,
                "max_memory": max_memory,
                "max_time": max_time,
                "results": results,
            }, status=status.HTTP_200_OK)

        except requests.exceptions.RequestException as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_result_with_retry(self, token, headers, retry_interval=1, max_retries=10):
        """
        Judge0에서 결과를 가져올 때 완료될 때까지 재시도
        """
        url = f"{self.JUDGE0_URL}{token}"
        for _ in range(max_retries):
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                result = response.json()
                if result.get("status", {}).get("description") not in ["Processing", "In Queue"]:
                    return result
            time.sleep(retry_interval)  # 결과 대기
        return None  # 최대 재시도 후 결과를 가져오지 못함
