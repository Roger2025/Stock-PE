# ==========================================
# 認證路由（登入/註冊/登出）
# ==========================================
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_user, logout_user

from app.models import User
from app import db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        confirm_password = request.form.get('confirm_password').strip()
        
        if password != confirm_password:
            flash("❌ 兩次輸入的密碼不一致，請重新確認。", "danger")
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash("❌ 該 Email 已經註冊過。", "danger")
            return redirect(url_for('auth.register'))
        
        # 預設賦予暱稱
        if not nickname:
            nickname = email.split('@')[0]
        
        new_user = User(email=email, nickname=nickname)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash(f"✅ 歡迎 {nickname}！專屬帳號創建成功，請登入以啟動終端。", "success")
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password').strip()
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            display_name = user.nickname if user.nickname else "創辦人" if user.email.lower().strip() == "A127038349@gmail.com" else "投資專家"
            flash(f"✅ 歡迎回來，{display_name}！戰情系統已成功解鎖。", "success")
            return redirect(url_for('main.index'))
        
        flash("❌ Email 或密碼錯誤。", "danger")
    
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
