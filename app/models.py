# ==========================================
# 會員與訂單數據庫模型
# ==========================================
from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    merchant_trade_no = db.Column(db.String(50), unique=True, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    user = db.relationship('User', backref='orders')


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    nickname = db.Column(db.String(100), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_vip = db.Column(db.Boolean, default=False)
    quota_remaining = db.Column(db.Integer, default=5)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # 訂閱生命週期追蹤
    vip_since = db.Column(db.DateTime, nullable=True)
    canceled_at = db.Column(db.DateTime, nullable=True)
    vip_expires_at = db.Column(db.DateTime, nullable=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def current_plan_name(self):
        from flask import current_app
        admin_email = current_app.jinja_env.globals.get('admin_email', 'A127038349@gmail.com')
        
        # 創辦人絕對識別
        if self.email.lower().strip() == admin_email.lower().strip():
            return "系統創辦人"
        
        if not self.is_vip:
            return "普通用戶"
        
        # 終身版
        if self.vip_since and not self.vip_expires_at:
            return "Pro 終身版"
        
        # 月付/年付
        if self.vip_since and self.vip_expires_at:
            days_diff = (self.vip_expires_at - self.vip_since).days
            if days_diff > 300:
                return "Pro 年費版"
            return "Pro 月費版"
        
        return "Pro 尊榮版"
