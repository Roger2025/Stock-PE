// ==========================================
// 🚀 攔截白屏跳轉邏輯 (SPA 轉場觸感)
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
    // 進入頁面瞬間確保極速平滑呈現
    document.body.classList.remove("page-is-changing");

    // 攔截所有普通連結點擊，注入 React 級淡出觸感
    document.querySelectorAll("a").forEach(link => {
        link.addEventListener("click", function(e) {
            const href = this.getAttribute("href");
            const target = this.getAttribute("target");
            
            // 排除另開視窗 (_blank)、錨點跳轉 (#) 或純 JS 觸發按鈕
            if (target === "_blank" || !href || href.startsWith("#") || href.startsWith("javascript")) {
                return;
            }

            e.preventDefault(); // 暫停冷酷的瞬間白屏跳轉
            document.body.classList.add("page-is-changing"); // 啟動平滑淡出

            // 等待淡出動畫執行完畢後，再優雅切換網址
            setTimeout(() => {
                window.location.href = href;
            }, 200); 
        });
    });

    // 攔截表單送出 (如登入、註冊、搜股分析)，按下瞬間畫面平滑淡出
    document.querySelectorAll("form").forEach(form => {
        form.addEventListener("submit", () => {
            document.body.classList.add("page-is-changing");
        });
    });
});

// 針對 Safari 往返快取 (BFCache) 的防禦：按上一頁時強制恢復畫面顯示
window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
        document.body.classList.remove("page-is-changing");
    }
});