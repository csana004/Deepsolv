from sqlalchemy import Column, String, Text
from database import Base

class Brand(Base):
    __tablename__ = "brands"

    website_url = Column(String, primary_key=True, index=True)
    store_name = Column(String)
    about = Column(Text)
    contact = Column(Text)
    faqs = Column(Text)
    shipping_policy = Column(Text)
    return_policy = Column(Text)
    refund_policy = Column(Text)
