// static/js/auth.js
document.addEventListener('DOMContentLoaded', function() {
    // Real-time validace formulářů
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        const inputs = form.querySelectorAll('input[required]');
        
        inputs.forEach(input => {
            // Validace při psaní
            input.addEventListener('input', function() {
                validateField(this);
            });
            
            // Validace při opuštění pole
            input.addEventListener('blur', function() {
                validateField(this);
            });
        });
    });
    
    // Funkce pro validaci pole
    function validateField(field) {
        const value = field.value.trim();
        const formGroup = field.closest('.form-group');
        
        // Odstranit předchozí chyby
        const existingError = formGroup.querySelector('.error-message');
        if (existingError) {
            existingError.remove();
        }
        
        field.classList.remove('error');
        
        // Validace podle typu pole
        if (field.type === 'email' && value) {
            if (!isValidEmail(value)) {
                showError(field, 'Zadejte platný email');
            }
        }
        
        if (field.type === 'password' && value) {
            if (value.length < 6) {
                showError(field, 'Heslo musí mít alespoň 6 znaků');
            }
        }
        
        if (field.name === 'username' && value) {
            if (value.length < 3) {
                showError(field, 'Uživatelské jméno musí mít alespoň 3 znaky');
            }
        }
    }
    
    // Funkce pro zobrazení chyby
    function showError(field, message) {
        field.classList.add('error');
        const formGroup = field.closest('.form-group');
        const errorElement = document.createElement('div');
        errorElement.className = 'error-message';
        errorElement.style.cssText = `
            color: #e74c3c;
            font-size: 0.85rem;
            margin-top: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        `;
        errorElement.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
        formGroup.appendChild(errorElement);
    }
    
    // Validace emailu
    function isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }
    
    // Tlačítko pro zobrazení/skrytí hesla
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach(input => {
        const formGroup = input.closest('.form-group');
        const toggleButton = document.createElement('button');
        toggleButton.type = 'button';
        toggleButton.innerHTML = '<i class="fas fa-eye"></i>';
        toggleButton.style.cssText = `
            position: absolute;
            right: 1rem;
            top: 50%;
            transform: translateY(-50%);
            background: none;
            border: none;
            color: #6c757d;
            cursor: pointer;
            padding: 0.5rem;
        `;
        
        formGroup.style.position = 'relative';
        formGroup.appendChild(toggleButton);
        
        toggleButton.addEventListener('click', function() {
            const type = input.type === 'password' ? 'text' : 'password';
            input.type = type;
            this.innerHTML = type === 'password' ? 
                '<i class="fas fa-eye"></i>' : 
                '<i class="fas fa-eye-slash"></i>';
        });
    });
});