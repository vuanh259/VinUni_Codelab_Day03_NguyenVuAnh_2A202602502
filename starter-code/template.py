"""
Lab #3: Baseline Chatbot vs ReAct Agent
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.
"""

import json
import re
from tools import TOOL_DEFINITIONS, TOOL_MAP, get_flight_info, get_weather_forecast

SYSTEM_PROMPT = """Bạn là một ReAct Agent thông minh hỗ trợ khách hàng Vingroup.
Bạn chỉ sử dụng các công cụ sau:
{tools}

Quy trình trả lời bắt buộc:
Thought: <Suy nghĩ bước tiếp theo>
Action: {{"name": "<tên tool>", "args": {{<tham số>}}}}
Observation: <Kết quả từ tool>
... (Lặp lại cho tới khi có đủ dữ liệu)
Final Answer: <Câu trả lời hoàn chỉnh cho khách hàng>
"""


class ChatbotBaseline:
    """Baseline LLM Chatbot (Không sử dụng ReAct Loop hay Tools)"""

    def query(self, user_input: str) -> str:
        # TODO: Trả về câu trả lời tĩnh hoặc gọi LLM 1 lượt (không dùng tool)
        return {
            "answer": f"[Chatbot Baseline] Trả lời cho: {user_input}",
            "tool_calls": [],
            "status": "success",
            "mode": "mock_baseline"
        }


class ReActAgent:
    """ReAct Agent có sử dụng Thought-Action-Observation Loop"""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace = []

    def _parse_price(self, text: str) -> int:
        """Chuyển các dạng '2 triệu', '1.5 triệu', '500k' thành VND."""
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(triệu|trieu|tr|k)", text.lower())

        if not match:
            return 5000000

        number = float(match.group(1).replace(",", "."))
        unit = match.group(2)

        if unit in ["triệu", "trieu", "tr"]:
            return int(number * 1000000)

        return int(number * 1000)

    def _parse_route(self, text: str):
        """Lấy sân bay đi và đến."""
        text_lower = text.lower()

        origin = None
        destination = None

        if "han" in text_lower or "hà nội" in text_lower:
            origin = "HAN"

        if "sgn" in text_lower or "sài gòn" in text_lower or "hồ chí minh" in text_lower:
            destination = "SGN"

        if "dad" in text_lower or "đà nẵng" in text_lower:
            destination = "DAD"

        return origin, destination

    def _parse_city_code(self, text: str) -> str:
        """Xác định thành phố cần tra thời tiết."""

        text_lower = text.lower()

        # Ưu tiên SGN vì câu hỏi multi-step có cả HAN và SGN.
        if (
            "sgn" in text_lower
            or "sài gòn" in text_lower
            or "hồ chí minh" in text_lower
        ):
            return "SGN"

        if "dad" in text_lower or "đà nẵng" in text_lower:
            return "DAD"

        if "han" in text_lower or "hà nội" in text_lower:
            return "HAN"

        return "SGN"

    def run(self, user_input: str) -> str:
        # TODO 1: Khởi tạo mảng lưu lịch sử conversation / traces
        self.trace = []

        user_lower = user_input.lower()

        # FAQ không cần tool
        if "chính sách" in user_lower or "đổi trả" in user_lower:
            answer = (
                "Chính sách đổi trả vé máy bay Vinpearl phụ thuộc vào "
                "điều kiện của từng loại vé và hãng hàng không. "
                "Bạn nên kiểm tra điều kiện vé khi đặt hoặc liên hệ "
                "bộ phận hỗ trợ của Vinpearl để được xác nhận."
            )

            self.trace.append({
                "iteration": 1,
                "thought": "Đây là câu hỏi FAQ, không cần sử dụng tool.",
                "action": None,
                "observation": None,
                "final_answer": answer
            })

            return {
                "answer": answer,
                "trace": self.trace,
                "iterations": 1,
                "status": "completed"
            }

        needs_flight = (
            "chuyến bay" in user_lower
            or "vé máy bay" in user_lower
            or ("han" in user_lower and ("sgn" in user_lower or "dad" in user_lower))
        )

        needs_weather = (
            "thời tiết" in user_lower
            or "mặc gì" in user_lower
            or "nhiệt độ" in user_lower
        )

        flight_result = None
        weather_result = None

        # TODO 2: Thiết lập vòng lặp while iteration < self.max_iterations
        iteration = 1

        while iteration <= self.max_iterations:

            # TODO 3 + TODO 4: Phân tích và thực thi Action
            # Bước 1: Tìm chuyến bay
            if needs_flight and flight_result is None:

                origin, destination = self._parse_route(user_input)
                max_price = self._parse_price(user_input)

                if origin is None:
                    origin = "HAN"

                if destination is None:
                    destination = "SGN"

                action = {
                    "name": "get_flight_info",
                    "args": {
                        "origin": origin,
                        "destination": destination,
                        "max_price": max_price
                    }
                }

                flight_result = TOOL_MAP["get_flight_info"](**action["args"])

                self.trace.append({
                    "iteration": iteration,
                    "thought": "Cần tìm chuyến bay phù hợp với yêu cầu.",
                    "action": action,
                    "observation": flight_result
                })

                if not needs_weather:
                    answer = self._format_flight_answer(flight_result)

                    self.trace.append({
                        "iteration": iteration,
                        "thought": "Đã đủ dữ liệu để trả lời.",
                        "action": None,
                        "observation": None,
                        "final_answer": answer
                    })

                    return {
                        "answer": answer,
                        "trace": self.trace,
                        "iterations": iteration,
                        "status": "completed"
                    }

                iteration += 1
                continue

            # Bước 2: Tìm thời tiết
            if needs_weather and weather_result is None:

                city_code = self._parse_city_code(user_input)

                action = {
                    "name": "get_weather_forecast",
                    "args": {
                        "city_code": city_code
                    }
                }

                weather_result = TOOL_MAP["get_weather_forecast"](**action["args"])

                self.trace.append({
                    "iteration": iteration,
                    "thought": "Cần lấy thông tin thời tiết để đưa ra gợi ý trang phục.",
                    "action": action,
                    "observation": weather_result
                })

                if not needs_flight:
                    answer = self._format_weather_answer(weather_result)

                    self.trace.append({
                        "iteration": iteration,
                        "thought": "Đã đủ dữ liệu để trả lời.",
                        "action": None,
                        "observation": None,
                        "final_answer": answer
                    })

                    return {
                        "answer": answer,
                        "trace": self.trace,
                        "iterations": iteration,
                        "status": "completed"
                    }

                iteration += 1
                continue

            # TODO 5: Đã có đủ Observation -> Final Answer
            if flight_result is not None and weather_result is not None:

                answer = self._format_combined_answer(
                    flight_result,
                    weather_result
                )

                self.trace.append({
                    "iteration": iteration,
                    "thought": "Đã có đủ thông tin chuyến bay và thời tiết.",
                    "action": None,
                    "observation": None,
                    "final_answer": answer
                })

                return {
                    "answer": answer,
                    "trace": self.trace,
                    "iterations": iteration,
                    "status": "completed"
                }

            break

        # Max iterations safeguard
        return {
            "answer": "Không thể hoàn thành yêu cầu trong số lần lặp cho phép.",
            "trace": self.trace,
            "iterations": self.max_iterations,
            "status": "max_iterations_reached"
        }

    def _format_flight_answer(self, flights):
        if not flights:
            return "Không tìm thấy chuyến bay phù hợp với yêu cầu."

        lines = ["Thông tin chuyến bay:"]

        for flight in flights:
            lines.append(
                f"- {flight.get('airline', '')} "
                f"({flight.get('flight_number', '')}): "
                f"{flight.get('departure_time', '')} - "
                f"{flight.get('price_vnd', 0):,} VNĐ"
            )

        return "\n".join(lines)

    def _format_weather_answer(self, weather):
        if not weather or "error" in weather:
            return "Không tìm thấy thông tin thời tiết."

        city = weather.get("city", "")
        temperature = weather.get("temperature_c", weather.get("temperature", ""))
        condition = weather.get("condition", "")
        recommendation = weather.get("recommendation", "")

        return (
            f"Thời tiết tại {city}: {temperature}°C, {condition}.\n"
            f"Gợi ý trang phục: {recommendation}"
        )

    def _format_combined_answer(self, flights, weather):
        flight_text = self._format_flight_answer(flights)

        weather_text = self._format_weather_answer(weather)

        return (
            f"1. {flight_text}\n\n"
            f"2. Thông tin thời tiết & trang phục:\n"
            f"{weather_text}"
        )


def main():
    user_query = "Tìm cho tôi chuyến bay từ HAN đi SGN dưới 2 triệu, rồi cho biết thời tiết SGN nên mặc gì?"

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING REACT AGENT ===")
    agent = ReActAgent(max_iterations=5)
    result = agent.run(user_query)

    print("Result:", result["answer"])
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
