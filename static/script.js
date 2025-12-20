document.addEventListener('DOMContentLoaded', () => {
    console.log("BudgetBuddy Script Loaded 🚀");

    /* =========================================
       1. GLOBAL THEME TOGGLE
       ========================================= */
    const themeBtn = document.getElementById('themeBtn');
    const body = document.body;

    // Load saved theme from memory
    if (localStorage.getItem('theme') === 'dark') {
        body.classList.add('dark-mode');
        if(themeBtn) themeBtn.textContent = '☀️';
    }

    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            body.classList.toggle('dark-mode');
            const isDark = body.classList.contains('dark-mode');

            // Save preference
            if (isDark) {
                localStorage.setItem('theme', 'dark');
                themeBtn.textContent = '☀️';
            } else {
                localStorage.setItem('theme', 'light');
                themeBtn.textContent = '🌙';
            }
            
            // Update the Dashboard Chart if the function exists
            if (typeof window.updateChartColors === "function") {
                window.updateChartColors(isDark);
            }
        });
    }

    /* =========================================
       2. SIDEBAR & MENU LOGIC (The Pop-up)
       ========================================= */
    const menuBtn = document.getElementById('menuBtn');
    const sidebar = document.getElementById('sidebar');
    const closeSidebarBtn = document.getElementById('closeSidebarBtn');
    const overlay = document.getElementById('overlay');

    // Open Sidebar
    if (menuBtn) {
        menuBtn.addEventListener('click', () => {
            sidebar.classList.add('active');
            overlay.classList.add('active');
        });
    }

    // Close Sidebar Function
    const closeSidebar = () => {
        sidebar.classList.remove('active');
        overlay.classList.remove('active');
    };

    // Trigger Close on 'X' button or Clicking the Dark Overlay
    if (closeSidebarBtn) closeSidebarBtn.addEventListener('click', closeSidebar);
    if (overlay) overlay.addEventListener('click', closeSidebar);


    /* =========================================
       3. LOGIN PAGE MODALS
       ========================================= */
    // Helper to connect buttons to modals
    const setupModal = (btnId, modalId) => {
        const btn = document.getElementById(btnId);
        const modal = document.getElementById(modalId);
        
        if (btn && modal) {
            btn.addEventListener('click', () => modal.classList.add('active'));
            
            // Close logic
            const closeBtn = modal.querySelector('.close-btn');
            if (closeBtn) closeBtn.addEventListener('click', () => modal.classList.remove('active'));
            
            // Close if clicking outside the box
            modal.addEventListener('click', (e) => {
                if (e.target === modal) modal.classList.remove('active');
            });
        }
    };

    // Activate Login/Signup Modals
    setupModal('btnSignup', 'modalSignup');
    setupModal('btnLogin', 'modalLogin');
});

/* =========================================
   4. DASHBOARD MODAL LOGIC
   ========================================= */

// 1. Logic for Dramatic Budget Modal (+ / -)
function quickUpdateBudget(action) {
    // A. Set the hidden input value to tell backend if we are Adding or Subtracting
    const actionInput = document.getElementById('incAction');
    if (actionInput) actionInput.value = action;

    // B. Handle the Drama (Emoji & Text)
    const emojiDiv = document.getElementById('incEmoji');
    const titleH2 = document.getElementById('incTitle');

    if (action === 'add') {
        if (emojiDiv) emojiDiv.innerText = "🤑"; // Happy Money Face
        if (titleH2) titleH2.innerText = "Increase Budget";
    } else {
        if (emojiDiv) emojiDiv.innerText = "😢"; // Crying Face
        if (titleH2) titleH2.innerText = "Decrease Budget";
    }

    // C. Open the Modal
    const modal = document.getElementById('incBudgetModal');
    if (modal) modal.classList.add('active');
}

// 2. Logic to Open Edit Transaction Modal
function openEditTransaction(id, desc, amount) {
    document.getElementById('edit_id').value = id;
    document.getElementById('edit_desc').value = desc;
    document.getElementById('edit_amount').value = amount;
    
    const modal = document.getElementById('editTransactionModal');
    if (modal) modal.classList.add("active");
}