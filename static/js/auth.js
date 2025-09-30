// static/js/auth.js - Kompletní řešení pro přihlášení a registraci
document.addEventListener('DOMContentLoaded', function() {
    initializeAuthForms();
});

function initializeAuthForms() {
    // Inicializace všech auth formulářů
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        setupFormValidation(form);
        setupPasswordToggle(form);
        setupSubmitHandler(form);
    });
    
    // Zpracování chybových zpráv
    handleErrorMessages();
}

function setupFormValidation(form) {
    const inputs = form.querySelectorAll('input[required]');
    
    inputs.forEach(input => {
        // Real-time validace při psaní
        input.addEventListener('input', function() {
            clearFieldError(this);
            validateField(this);
        });
        
        // Validace při opuštění pole
        input.addEventListener('blur', function() {
            validateField(this);
        });
    });
}

function validateField(field) {
    const value = field.value.trim();
    const formGroup = field.closest('.form-group');
    
    // Odstranit předchozí chyby
    clearFieldError(field);
    
    // Validace podle typu pole
    let isValid = true;
    let errorMessage = '';
    
    switch (field.type) {
        case 'email':
            if (value && !isValidEmail(value)) {
                isValid = false;
                errorMessage = 'Zadejte platný email';
            }
            break;
            
        case 'password':
            if (value && value.length < 6) {
                isValid = false;
                errorMessage = 'Heslo musí mít alespoň 6 znaků';
            }
            break;
            
        case 'text':
            if (field.name === 'username' && value) {
                if (value.length < 3) {
                    isValid = false;
                    errorMessage = 'Uživatelské jméno musí mít alespoň 3 znaky';
                } else if (!/^[a-zA-Z0-9_]+$/.test(value)) {
                    isValid = false;
                    errorMessage = 'Uživatelské jméno může obsahovat pouze písmena, čísla a podtržítka';
                }
            }
            break;
    }
    
    if (!isValid) {
        showFieldError(field, errorMessage);
    } else if (value) {
        showFieldSuccess(field);
    }
    
    return isValid;
}

function showFieldError(field, message) {
    field.classList.add('error');
    const formGroup = field.closest('.form-group');
    const errorElement = document.createElement('div');
    errorElement.className = 'error-message';
    errorElement.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
    formGroup.appendChild(errorElement);
}

function showFieldSuccess(field) {
    field.classList.add('success');
}

function clearFieldError(field) {
    field.classList.remove('error', 'success');
    const formGroup = field.closest('.form-group');
    const existingError = formGroup.querySelector('.error-message');
    if (existingError) {
        existingError.remove();
    }
}

function setupPasswordToggle(form) {
    const passwordInputs = form.querySelectorAll('input[type="password"]');
    
    passwordInputs.forEach(input => {
        const formGroup = input.closest('.form-group');
        
        // Vytvořit tlačítko pro zobrazení/skrytí hesla
        const toggleButton = document.createElement('button');
        toggleButton.type = 'button';
        toggleButton.className = 'password-toggle';
        toggleButton.innerHTML = '<i class="fas fa-eye"></i>';
        toggleButton.setAttribute('aria-label', 'Zobrazit heslo');
        
        formGroup.style.position = 'relative';
        formGroup.appendChild(toggleButton);
        
        // Přepínání viditelnosti hesla
        toggleButton.addEventListener('click', function() {
            const isPassword = input.type === 'password';
            input.type = isPassword ? 'text' : 'password';
            this.innerHTML = isPassword ? 
                '<i class="fas fa-eye-slash"></i>' : 
                '<i class="fas fa-eye"></i>';
            this.setAttribute('aria-label', 
                isPassword ? 'Skrýt heslo' : 'Zobrazit heslo');
        });
    });
}

function setupSubmitHandler(form) {
    let submitAttempts = 0;
    const maxAttempts = 5;
    
    form.addEventListener('submit', function(e) {
        const submitBtn = form.querySelector('button[type="submit"]');
        const inputs = form.querySelectorAll('input[required]');
        
        // Validace všech polí
        let isFormValid = true;
        inputs.forEach(input => {
            if (!validateField(input)) {
                isFormValid = false;
            }
        });
        
        if (!isFormValid) {
            e.preventDefault();
            showGlobalMessage('Opravte chyby ve formuláři', 'error');
            return;
        }
        
        // Kontrola počtu pokusů
        submitAttempts++;
        if (submitAttempts > maxAttempts) {
            e.preventDefault();
            showGlobalMessage(`Překročen limit pokusů. Zkuste to za 15 minut.`, 'error');
            submitBtn.disabled = true;
            startCooldown(submitBtn, 900); // 15 minut
            return;
        }
        
        // Loading stav
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Zpracovávání...';
        }
    });
}

function handleErrorMessages() {
    const errorMessage = document.querySelector('.auth-message.error');
    if (errorMessage) {
        const authCard = document.querySelector('.auth-card');
        
        // Efekt třesení
        authCard.classList.add('shake');
        setTimeout(() => {
            authCard.classList.remove('shake');
        }, 500);
        
        // Zvýraznit políčka
        const inputs = document.querySelectorAll('input');
        inputs.forEach(input => {
            input.style.borderColor = '#e74c3c';
            input.style.background = '#fdf2f2';
        });
        
        // Resetovat styly při psaní
        inputs.forEach(input => {
            input.addEventListener('input', function() {
                this.style.borderColor = '';
                this.style.background = '';
            });
        });
    }
}

function showGlobalMessage(message, type) {
    // Odstranit existující zprávu
    const existingMessage = document.querySelector('.auth-message.global');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    // Vytvořit novou zprávu
    const messageDiv = document.createElement('div');
    messageDiv.className = `auth-message global ${type}`;
    
    const icon = getMessageIcon(type);
    messageDiv.innerHTML = `<i class="fas fa-${icon}"></i> ${message}`;
    
    // Přidat před formulář
    const form = document.querySelector('form');
    if (form) {
        form.parentNode.insertBefore(messageDiv, form);
    }
    
    // Efekt třesení pro chyby
    if (type === 'error') {
        const authCard = document.querySelector('.auth-card');
        if (authCard) {
            authCard.classList.add('shake');
            setTimeout(() => {
                authCard.classList.remove('shake');
            }, 500);
        }
    }
    
    // Automatické zmizení pro info/success zprávy
    if (type === 'info' || type === 'success') {
        setTimeout(() => {
            messageDiv.remove();
        }, 5000);
    }
}

function getMessageIcon(type) {
    const icons = {
        'error': 'exclamation-triangle',
        'success': 'check-circle',
        'info': 'info-circle',
        'warning': 'exclamation-circle'
    };
    return icons[type] || 'info-circle';
}

function startCooldown(button, seconds) {
    let timeLeft = seconds;
    const originalHTML = button.innerHTML;
    
    const cooldownInterval = setInterval(() => {
        const minutes = Math.floor(timeLeft / 60);
        const seconds = timeLeft % 60;
        
        button.innerHTML = 
            `<i class="fas fa-clock"></i> Zkuste to za ${minutes}:${seconds.toString().padStart(2, '0')}`;
        
        if (timeLeft <= 0) {
            clearInterval(cooldownInterval);
            button.disabled = false;
            button.innerHTML = originalHTML;
        }
        
        timeLeft--;
    }, 1000);
}

function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// Utility funkce pro práci s formuláři
function getFormData(form) {
    const formData = new FormData(form);
    const data = {};
    for (let [key, value] of formData.entries()) {
        data[key] = value;
    }
    return data;
}

function resetForm(form) {
    form.reset();
    form.querySelectorAll('input').forEach(input => {
        clearFieldError(input);
    });
}

// Export funkcí pro případné použití v jiných souborech
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeAuthForms,
        validateField,
        showGlobalMessage,
        isValidEmail
    };
}