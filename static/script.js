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
       2. SIDEBAR & MENU LOGIC
       ========================================= */
    const menuBtn = document.getElementById('menuBtn');
    const sidebar = document.getElementById('sidebar');
    const closeSidebarBtn = document.getElementById('closeSidebarBtn');
    const overlay = document.getElementById('overlay');

    // Open Sidebar
    if (menuBtn) {
        menuBtn.addEventListener('click', () => {
            sidebar.classList.add('active');
            if (overlay) overlay.classList.add('active');
        });
    }

    // Close Sidebar Function
    const closeSidebar = () => {
        sidebar.classList.remove('active');
        if (overlay) overlay.classList.remove('active');
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
    const actionInput = document.getElementById('incAction');
    if (actionInput) actionInput.value = action;

    const emojiDiv = document.getElementById('incEmoji');
    const titleH2 = document.getElementById('incTitle');

    if (action === 'add') {
        if (emojiDiv) emojiDiv.innerText = "🤑"; // Happy Money Face
        if (titleH2) titleH2.innerText = "Increase Budget";
    } else {
        if (emojiDiv) emojiDiv.innerText = "😢"; // Crying Face
        if (titleH2) titleH2.innerText = "Decrease Budget";
    }

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

/* =========================================
   5. FASTAPI BACKGROUND REQUESTS
   ========================================= */

// 1. UPDATE BUDGET API CALL
const budgetForm = document.getElementById('updateBudgetForm');
if (budgetForm) {
    budgetForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const budgetAmount = document.querySelector('input[name="budget"]').value;

        try {
            const response = await fetch('/api/v1/budget', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Client-ID': CLIENT_ID
                },
                body: JSON.stringify({ budget: parseFloat(budgetAmount) })
            });

            if (response.ok) {
                window.location.reload(); 
            } else {
                alert("Error updating budget: " + await response.text());
            }
        } catch (error) {
            console.error("Network error:", error);
        }
    });
}

// 2. ADD EXPENSE API CALL
const expenseForm = document.getElementById('addExpenseForm');
if (expenseForm) {
    expenseForm.addEventListener('submit', async function(e) {
        e.preventDefault(); 

        const formData = new FormData(this);
        
        // Check if the toggle is checked
        const recurringToggle = document.getElementById('is_recurring');
        const isRecurring = recurringToggle ? recurringToggle.checked : false;
        
        // Automatically grab the day of the month from the selected date
        let recurringDay = null;
        if (isRecurring) {
            const dateVal = formData.get('date') || new Date().toISOString().split('T')[0];
            recurringDay = parseInt(dateVal.split('-')[2]); 
        }

        const data = {
            amount: parseFloat(formData.get('amount')),
            category: formData.get('category'),
            description: formData.get('description'),
            date: formData.get('date') || null,
            is_recurring: isRecurring,
            recurring_day: recurringDay
        };

        try {
            const response = await fetch('/api/v1/expenses', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Client-ID': CLIENT_ID
                },
                body: JSON.stringify(data)
            });

            if (response.ok) {
                window.location.reload();
            } else {
                alert("Error adding expense: " + await response.text());
            }
        } catch (error) { 
            console.error("Network error:", error); 
        }
    });
}

// 3. EDIT EXPENSE API CALL
const editForm = document.getElementById('editExpenseForm');
if (editForm) {
    editForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        const expenseId = formData.get('id'); 
        
        const data = {
            amount: parseFloat(formData.get('amount')),
            category: formData.get('category') || "Other",
            description: formData.get('description')
        };

        try {
            const response = await fetch(`/api/v1/expenses/${expenseId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Client-ID': CLIENT_ID
                },
                body: JSON.stringify(data)
            });

            if (response.ok) {
                window.location.reload();
            } else {
                alert("Error updating expense: " + await response.text());
            }
        } catch (error) { 
            console.error("Network error:", error); 
        }
    });
}

// 4. SMART DELETE EXPENSE API CALL
window.openDeleteModal = function(id, description, isTemplate) {
    document.getElementById('delete_expense_id').value = id;
    
    const askBox = document.getElementById('smart-ask-box');
    const normalText = document.getElementById('normal-delete-text');
    
    // Clean up the string coming from the HTML/Database
    const isRecurring = (isTemplate === '1' || isTemplate === 'True' || isTemplate === 'true');
    
    // Check if the item is a recurring template
    if (isRecurring) {
        if(askBox) askBox.style.display = 'block';     
        if(normalText) normalText.style.display = 'none';  
        document.getElementById('delete-desc-preview').innerText = `("${description}")`;
        document.querySelector('input[name="delete_mode"][value="single"]').checked = true;
    } else {
        if(askBox) askBox.style.display = 'none';      
        if(normalText) normalText.style.display = 'block'; 
        
        // Invisibly select 'single' so the backend doesn't accidentally wipe subscriptions
        const singleRadio = document.querySelector('input[name="delete_mode"][value="single"]');
        if (singleRadio) singleRadio.checked = true;
    }
    
    const modal = document.getElementById('deleteModal');
    if(modal) modal.classList.add('active');
};

// 5. CONFIRM DELETE BUTTON
const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
if (confirmDeleteBtn) {
    confirmDeleteBtn.addEventListener('click', async function() {
        const expenseId = document.getElementById('delete_expense_id').value;
        
        // Check which radio button is selected
        const checkedMode = document.querySelector('input[name="delete_mode"]:checked');
        const deleteMode = checkedMode ? checkedMode.value : 'single';
        const stopRecurring = (deleteMode === 'all'); 
        
        try {
            const response = await fetch(`/api/v1/expenses/${expenseId}?stop_recurring=${stopRecurring}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Client-ID': CLIENT_ID
                }
            });

            if (response.ok) {
                const modal = document.getElementById('deleteModal');
                if(modal) modal.classList.remove('active');
                window.location.reload();
            } else {
                const err = await response.json();
                alert("Error deleting expense: " + (err.detail || "Unknown error"));
            }
        } catch (error) {
            console.error("Network error:", error);
            alert("Network error. Please try again.");
        }
    });
}
