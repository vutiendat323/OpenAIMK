import pytest
from test_service import stamp

from trendcoffee.service import Service


@pytest.fixture
def svc(tmp_path):
    service = Service(tmp_path / "test.db")
    service.ingest(
        {
            "knowledge": [
                {
                    "id": "address",
                    "title": "Địa chỉ",
                    "text": "Quán ở số 3 Nguyễn Công Trứ.",
                    "source_url": "https://trendcoffee.net/contact",
                    "verified_at": stamp(),
                    "approved": True,
                    "evidence": "published_ui",
                },
                {
                    "id": "secret",
                    "title": "Khuyến mãi",
                    "text": "Miễn phí tất cả đồ uống.",
                    "source_url": "https://trendcoffee.net/",
                    "verified_at": stamp(),
                    "approved": False,
                    "evidence": "unverified",
                },
                {
                    "id": "old",
                    "title": "Ưu đãi cũ",
                    "text": "Ưu đãi giảm giá sinh nhật.",
                    "source_url": "https://trendcoffee.net/",
                    "verified_at": stamp(-10),
                    "expires_at": stamp(-1),
                    "approved": True,
                    "evidence": "published_ui",
                },
            ],
            "menu": {
                "items": [
                    {
                        "id": "coffee",
                        "name": "Cà phê sữa",
                        "price_vnd": 30000,
                        "options": {"ice": ["ít", "vừa"]},
                        "availability": "unknown",
                        "source_url": "https://trendcoffee.net/api/latest/menu",
                        "verified_at": stamp(),
                    },
                    {
                        "id": "sold",
                        "name": "Hết món",
                        "price_vnd": 20000,
                        "options": {},
                        "availability": "sold_out",
                        "source_url": "https://trendcoffee.net/api/latest/menu",
                        "verified_at": stamp(),
                    },
                ]
            },
        }
    )
    return service
