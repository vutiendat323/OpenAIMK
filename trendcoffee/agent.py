"""Fast local routing. Optional models select evidence; business answers remain sourced."""

import re
import time

from .service import ServiceError, normalize


class Agent:
    def __init__(self, service, semantic=None):
        self.service, self.semantic = service, semantic

    async def chat(self, token, message):
        started = time.perf_counter()
        preferences = self.service.memory(token)  # Authenticate every route.
        query = normalize(message).strip()
        query = re.sub(r"\bcafe\b", "ca phe", query)
        result = {
            "reply": "",
            "intent": "unknown",
            "sources": [],
            "mode": "merchant_api" if self.service.merchant else "local_queue_only",
        }
        if any(
            term in query
            for term in [
                "chuyen khoan roi",
                "da thanh toan",
                "da chuyen tien",
                "da chuyen khoan",
                "danh dau don da thanh toan",
            ]
        ):
            facts = [
                doc
                for doc in self.service.search("đã trả tiền chưa cập nhật biên lai")
                if doc["id"] == "payment_support"
            ]
            result.update(
                intent="payment_support",
                sources=facts,
                reply="Mình chưa xác minh được tiền vào. Chưa chuyển tiền lần nữa khi giao dịch chưa rõ. "
                + (facts[0]["text"] if facts else "Bạn có thể lưu yêu cầu để nhân viên đối soát."),
            )
        elif any(
            term in query for term in ["tien do", "don cua toi", "don den dau", "trang thai don"]
        ):
            progress = self.service.progress(token)
            result.update(
                intent="progress",
                progress=progress,
                reply="Đây là tiến độ ghi nhận trong hệ thống hỗ trợ nội bộ. Yêu cầu chờ tiếp nhận chưa đồng nghĩa quán đã nhận đơn."
                if progress["orders"]
                else "Phiên này chưa có yêu cầu đặt món đã gửi.",
            )
        elif any(term in query for term in ["xoa bo nho", "quen khau vi", "xoa khau vi"]):
            self.service.forget(token)
            result.update(intent="forget", reply="Đã xóa sở thích đã lưu trong phiên khách này.")
        elif any(term in query for term in ["nho khau vi", "luu khau vi", "nho so thich"]):
            result.update(
                intent="memory_consent",
                reply="Bạn nhập sở thích cụ thể vào mục Bộ nhớ và chọn đồng ý lưu. Dữ liệu chỉ gắn với phiên khách này, tối đa 30 ngày và có thể xóa bất cứ lúc nào.",
            )
        elif re.search(
            r"\b(?:ban trong|tinh trang ban|trang thai ban|con ban|ban nao)\b"
            r"|\bban\s+\d+\s+(?:hien|con|co|trong|dang|da|duoc)\b",
            query,
        ):
            table = re.search(r"\bban\s+(\d+)\b", query)
            try:
                live = self.service.tables(table[1] if table else None)
                if table:
                    statuses = {
                        "available": "đang trống",
                        "reserved": "đã được giữ",
                        "occupied": "đang có khách",
                    }
                    current = live["tables"]
                    reply = (
                        f"Theo cập nhật từ quán, bàn {current[0]['name']} "
                        + statuses.get(current[0]["status"], "chưa xác định được tình trạng")
                        + "."
                        if current
                        else "Quán chưa có bàn mang số này trong danh sách hiện tại."
                    )
                elif live["first_available"]:
                    reply = (
                        f"Theo cập nhật từ quán, hiện có {live['available_count']} bàn trống; "
                        f"bàn {live['first_available']['name']} là bàn trống đầu tiên."
                    )
                else:
                    reply = "Theo cập nhật từ quán, hiện chưa có bàn được báo là trống."
                result.update(
                    intent="tables",
                    tables=live,
                    reply=reply,
                    sources=[
                        {
                            "title": "Tình trạng bàn trực tiếp từ quán",
                            "source_url": live["source_url"],
                            "verified_at": live["fetched_at"],
                        }
                    ],
                )
            except ServiceError as exc:
                result.update(
                    intent="tables_unavailable",
                    error=exc.code,
                    reply="Chưa lấy được tình trạng bàn hiện tại từ quán. Bạn thử lại hoặc nhờ nhân viên hỗ trợ nhé.",
                )
        elif any(
            term in query
            for term in ["thieu mon", "sai mon", "khieu nai", "hoan tien", "huy don", "nhan vien"]
        ):
            facts = self.service.search(message)
            result.update(
                intent="support",
                sources=facts[:2],
                reply="Mình có thể lưu yêu cầu để nhân viên xử lý trong hàng đợi nội bộ. Bạn chọn “Cần hỗ trợ”; chưa có kết nối để tự hủy đơn hay hoàn tiền trên website quán.",
            )
        elif (
            "mang di" in query
            or any(term in query for term in ["tai ban", "tai quan"])
            or re.search(r"\bban\s+[a-z0-9]+", query)
        ) and self.service.working_draft(token):
            result.update(self._order(token, query, pending=self.service.working_draft(token)))
        elif (
            any(term in query for term in ["cho ", "dat ", "lay ", "goi "])
            and any(normalize(item["name"]) in query for item in self.service.menu())
            and not any(
                term in query
                for term in [
                    "cach dat",
                    "huong dan",
                    "dia chi",
                    "o dau",
                    "cho biet",
                    "gia bao nhieu",
                    "goi y",
                    "de xuat",
                ]
            )
        ):
            result.update(self._order(token, query))
        elif any(
            term in query
            for term in [
                "menu",
                "thuc don",
                "mon gi",
                "do uong",
                "gia bao nhieu",
                "goi y",
                "de xuat",
                "tu van",
            ]
        ):
            result.update(self._catalog_response(query))
        elif query in ["hi", "hello", "xin chao", "chao", "chao ban"]:
            result.update(
                intent="greeting",
                reply="Chào bạn, mình là trợ lý Trend Coffee. Bạn muốn xem thực đơn, chọn món hay cần hỗ trợ đơn hàng?",
            )
        else:
            # Expand intents locally before spending a model round trip.
            lookup = message
            if any(term in query for term in ["cach dat", "huong dan dat", "dat mon the nao"]):
                lookup = "Cách đặt món trên website"
            elif any(
                term in query for term in ["o dau", "dia chi", "duong nao", "address", "where"]
            ):
                lookup = "địa chỉ"
            elif any(term in query for term in ["may gio", "mo cua", "gio hoat dong"]):
                lookup = "giờ mở cửa"
            elif any(term in query for term in ["thanh toan", "qr", "tra tien"]):
                lookup = "thanh toán QR"
            facts = self.service.search(lookup)
            # One matching common word is not sufficient evidence for arbitrary questions.
            common = {
                "toi",
                "ban",
                "cho",
                "co",
                "la",
                "va",
                "cua",
                "the",
                "nao",
                "gi",
                "khong",
                "duoc",
                "voi",
                "hay",
                "ai",
            }
            terms = set(re.findall("[a-z0-9]+", normalize(lookup))) - common
            facts = [
                fact
                for fact in facts
                if terms
                & set(re.findall("[a-z0-9]+", normalize(fact["title"] + " " + fact["text"])))
            ]
            if self.semantic and not facts:
                facts = await self.semantic.select(message, self.service)
            if facts:
                result.update(
                    intent="knowledge",
                    sources=facts[:2],
                    reply="\n\n".join(fact["text"] for fact in facts[:2]),
                )
            else:
                result["reply"] = (
                    "Mình chưa có thông tin đã kiểm chứng cho câu hỏi này. Bạn có thể xem thực đơn hoặc lưu yêu cầu hỗ trợ để nhân viên kiểm tra."
                )
        if preferences and result["intent"] == "menu":
            result["preferences"] = preferences
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return result

    def _order(self, token, query, pending=None):
        if re.search(r"\b(khong|dung|chua)\s+(dat|goi|lay|mua)\b", query):
            self.service.working_draft(token, clear=True)
            return {
                "intent": "order_not_requested",
                "reply": "Mình chưa tạo yêu cầu đặt món và đã bỏ bản nháp hội thoại. Bạn có thể tiếp tục xem thực đơn.",
            }
        numbers = {
            "mot": 1,
            "hai": 2,
            "ba": 3,
            "bon": 4,
            "nam": 5,
            "sau": 6,
            "bay": 7,
            "tam": 8,
            "chin": 9,
            "muoi": 10,
        }
        matches = []
        occupied = []
        for item in sorted(self.service.menu(), key=lambda x: len(x["name"]), reverse=True):
            name = normalize(item["name"])
            for match in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", query):
                if any(match.start() < end and match.end() > start for start, end in occupied):
                    continue
                occupied.append((match.start(), match.end()))
                prefix = query[max(0, match.start() - 24) : match.start()]
                quantity = re.search(
                    r"(\d+|mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi)\s*(?:ly|coc|phan|chai)?\s*$",
                    prefix,
                )
                matches.append(
                    {
                        "item_id": item["id"],
                        "quantity": (
                            int(quantity[1]) if quantity[1].isdigit() else numbers[quantity[1]]
                        )
                        if quantity
                        else 1,
                        "options": {},
                    }
                )
        matches = matches or pending
        if not matches:
            return {
                "intent": "clarify_order",
                "reply": "Bạn chọn tên món và số lượng từ thực đơn đã nhập nhé. Mình cần đúng lựa chọn/kích cỡ trước khi tính tiền.",
            }
        # Recognize a small grammar completely. Unconsumed text may be an unsupported
        # modifier; asking is safer than silently changing what the customer requested.
        remainder = query
        for start, end in sorted(occupied, reverse=True):
            remainder = remainder[:start] + " " * (end - start) + remainder[end:]
        remainder = re.sub(r"\bkhong mang di\b", " ", remainder)
        remainder = re.sub(r"\b(?:tai ban|tai quan)\b", " ", remainder)
        remainder = re.sub(r"\b(?:tai |o )?ban\s+[a-z0-9]+\b", " ", remainder)
        words = "|".join(numbers)
        if re.search(r"(?<!\w)-\s*\d|\d+[.,]\d+", remainder) or re.search(
            r"\b(?:" + words + r")\s+(?:" + words + r")\b", remainder
        ):
            self.service.working_draft(token, clear=True)
            return {
                "intent": "clarify_quantity",
                "reply": "Bạn ghi số lượng bằng số nguyên dương giúp mình, ví dụ 2 ly. Mình chưa lập bản tạm tính để tránh hiểu sai số lượng.",
            }
        allowed = {
            "cho",
            "minh",
            "toi",
            "tao",
            "muon",
            "dat",
            "goi",
            "lay",
            "mua",
            "ly",
            "coc",
            "phan",
            "chai",
            "va",
            "mang",
            "di",
            "nhe",
            "nha",
            "a",
            "voi",
            "giup",
            "xin",
        } | set(numbers)
        if any(
            word not in allowed and not word.isdigit()
            for word in re.findall(r"[a-z0-9]+", remainder)
        ):
            self.service.working_draft(token, clear=True)
            return {
                "intent": "clarify_options",
                "reply": "Mình cần kiểm tra phần tùy chỉnh bạn vừa yêu cầu. Chưa có bản tạm tính; bạn chọn tùy chọn được hỗ trợ từ thực đơn hoặc nhờ nhân viên xác nhận nhé.",
            }
        try:
            self.service.working_draft(token, matches)
            table_text = re.sub(r"\btai ban(?=\s+(?:a|nhe|nha|voi|giup)\b|$)", "", query)
            table = re.search(r"\bban\s+([a-z0-9]+)\b", table_text)
            if "mang di" in query and "khong mang di" not in query:
                quote = self.service.quote(token, matches, fulfillment="takeaway")
            elif table:
                quote = self.service.quote(
                    token, matches, fulfillment="at_table", table_label="Bàn " + table[1]
                )
            elif any(term in query for term in ["tai ban", "tai quan"]):
                quote = self.service.quote(token, matches, fulfillment="at_table")
            else:
                return {
                    "intent": "clarify_fulfillment",
                    "reply": "Bạn dùng tại bàn hay mang đi? Mình đã giữ các món bạn chọn trong phiên này.",
                }
            self.service.working_draft(token, clear=True)
        except ServiceError as exc:
            return {
                "intent": "order_unavailable",
                "error": exc.code,
                "reply": "Chưa thể lập yêu cầu với dữ liệu hiện tại. Cần kiểm tra lại giá, món còn bán và tùy chọn với quán.",
            }
        return {
            "intent": "quote",
            "quote": quote,
            "reply": f"Tạm tính {quote['total_vnd']:,}đ theo giá niêm yết. Mình đang gửi yêu cầu. "
            + (
                "QR thanh toán sẽ hiện ngay trên màn hình."
                if quote["mode"] == "merchant_api"
                else "Yêu cầu sẽ vào hàng đợi nội bộ, chờ nhân viên tiếp nhận."
            ),
        }

    def _catalog_response(self, query):
        items = self.service.menu()
        matching = [item for item in items if normalize(item["name"]) in query]
        recommendation = any(term in query for term in ["goi y", "de xuat", "tu van"])
        if matching:
            items = matching
        else:
            categories = {item.get("category", "") for item in items} - {""}
            selected = [
                category
                for category in categories
                if re.search(
                    r"\b" + re.escape(normalize(category).removeprefix("mon ")) + r"\b", query
                )
            ]
            if selected:
                items = [item for item in items if item.get("category") in selected]
        budget = re.search(
            r"(?:duoi|toi da|khong qua|ngan sach)\s+(\d+)\s*(k|nghin|ngan|dong|d)?\b", query
        )
        if budget:
            ceiling = int(budget[1]) * (1000 if budget[2] in ["k", "nghin", "ngan"] else 1)
            items = [item for item in items if item["price_vnd"] <= ceiling]
        items = [item for item in items if not item["stale"] and item["availability"] != "sold_out"]
        if recommendation:
            items = sorted(items, key=lambda item: (item["price_vnd"], item["name"]))[:3]
        if not items:
            reply = "Chưa có món phù hợp với yêu cầu này. Bạn muốn chọn mức giá hoặc loại đồ uống khác không?"
        elif recommendation or matching:
            reply = "; ".join(f"{item['name']}: {item['price_vnd']:,}đ" for item in items[:2])
            reply += ". Bạn chọn món nào?"
        else:
            reply = (
                "Có "
                + "; ".join(f"{item['name']}: {item['price_vnd']:,}đ" for item in items[:2])
                + ". Bạn xem thêm trong thực đơn nhé."
            )
        sources = [
            {
                "id": item["id"],
                "title": item["name"],
                "source_url": item["source_url"],
                "verified_at": item["verified_at"],
            }
            for item in items[:2]
        ]
        return {
            "intent": "recommendation" if recommendation else "menu",
            "menu": items,
            "sources": sources,
            "reply": reply,
        }
