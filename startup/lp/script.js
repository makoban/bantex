// ========================================
// Navigation Toggle (Mobile)
// ========================================
const navToggle = document.querySelector('.nav-toggle');
const navMenu = document.querySelector('.nav-menu');

if (navToggle && navMenu) {
    navToggle.addEventListener('click', () => {
        navMenu.classList.toggle('active');
        navToggle.classList.toggle('active');
    });

    // Close menu when clicking a link
    navMenu.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
            navMenu.classList.remove('active');
            navToggle.classList.remove('active');
        });
    });
}

// ========================================
// Smooth Scroll for Anchor Links
// ========================================
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            const headerOffset = 70;
            const elementPosition = target.getBoundingClientRect().top;
            const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

            window.scrollTo({
                top: offsetPosition,
                behavior: 'smooth'
            });
        }
    });
});

// ========================================
// Intersection Observer for Animations
// ========================================
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('animate-in');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Observe all animatable elements
document.querySelectorAll('.problem-card, .solution-card, .service-card, .subsidy-card, .profile-card').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(30px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
});

// Add animate-in styles
const style = document.createElement('style');
style.textContent = `
    .animate-in {
        opacity: 1 !important;
        transform: translateY(0) !important;
    }
`;
document.head.appendChild(style);

// ========================================
// Navigation Background on Scroll
// ========================================
const nav = document.querySelector('.nav');
let lastScroll = 0;

window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;

    if (currentScroll > 100) {
        nav.style.background = 'rgba(15, 23, 42, 0.98)';
        nav.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1)';
    } else {
        nav.style.background = 'rgba(15, 23, 42, 0.95)';
        nav.style.boxShadow = 'none';
    }

    lastScroll = currentScroll;
});

// ========================================
// Form Confirmation Modal & Email
// ========================================
function showConfirmation() {
    const form = document.getElementById('contactForm');
    const name = document.getElementById('name').value;
    const email = document.getElementById('email').value;

    if (!name || !email) {
        alert('お名前とメールアドレスは必須です');
        return;
    }

    const company = document.getElementById('company').value || '（未入力）';
    const tel = document.getElementById('tel').value || '（未入力）';
    const interest = document.getElementById('interest').value || '（未選択）';
    const message = document.getElementById('message').value || '（未入力）';

    const details = document.getElementById('confirmDetails');
    details.innerHTML = `
        <div class="confirm-row"><span class="confirm-label">会社名:</span><span>${company}</span></div>
        <div class="confirm-row"><span class="confirm-label">お名前:</span><span>${name}</span></div>
        <div class="confirm-row"><span class="confirm-label">メール:</span><span>${email}</span></div>
        <div class="confirm-row"><span class="confirm-label">電話番号:</span><span>${tel}</span></div>
        <div class="confirm-row"><span class="confirm-label">興味のあるサービス:</span><span>${interest}</span></div>
        <div class="confirm-row"><span class="confirm-label">ご相談内容:</span><span>${message}</span></div>
    `;

    document.getElementById('confirmModal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('confirmModal').style.display = 'none';
}

function sendEmail() {
    const company = document.getElementById('company').value || '';
    const name = document.getElementById('name').value;
    const email = document.getElementById('email').value;
    const tel = document.getElementById('tel').value || '';
    const interest = document.getElementById('interest').value || '';
    const message = document.getElementById('message').value || '';

    // Web3Forms API key
    const accessKey = '18e5fc30-492e-4cbc-994f-50baddd58d4c';

    const formData = {
        access_key: accessKey,
        subject: '【LP】無料診断のお申し込み',
        from_name: 'Bantex LP',
        company: company,
        name: name,
        email: email,
        tel: tel,
        interest: interest,
        message: message
    };

    // Show loading state
    const submitBtn = document.querySelector('.btn-primary');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = '送信中...';
    submitBtn.disabled = true;

    fetch('https://api.web3forms.com/submit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            closeModal();
            alert('お申し込みありがとうございます！\n2営業日以内にご連絡いたします。');
            document.getElementById('contactForm').reset();
        } else {
            throw new Error(result.message || '送信に失敗しました');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('送信に失敗しました。\nお手数ですが、直接 info@bantex.jp までご連絡ください。');
    })
    .finally(() => {
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    });
}

// ========================================
// Counter Animation for Stats
// ========================================
function animateCounter(element, target, suffix = '') {
    let current = 0;
    const increment = target / 50;
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            element.textContent = target + suffix;
            clearInterval(timer);
        } else {
            element.textContent = Math.floor(current) + suffix;
        }
    }, 20);
}

// Observe stat elements for counter animation
const statObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const value = entry.target.textContent;
            // Only animate numeric values
            if (/^\d+/.test(value)) {
                const num = parseInt(value.replace(/\D/g, ''));
                const suffix = value.replace(/\d/g, '');
                animateCounter(entry.target, num, suffix);
            }
            statObserver.unobserve(entry.target);
        }
    });
}, { threshold: 0.5 });

document.querySelectorAll('.profile-number').forEach(el => {
    statObserver.observe(el);
});

// ========================================
// Parallax Effect for Hero Background
// ========================================
const heroBg = document.querySelector('.hero-bg');

if (heroBg) {
    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        heroBg.style.transform = `translateY(${scrolled * 0.3}px)`;
    });
}

// ========================================
// Dynamic Year in Footer
// ========================================
const yearElement = document.querySelector('.footer-bottom p');
if (yearElement) {
    const currentYear = new Date().getFullYear();
    yearElement.innerHTML = yearElement.innerHTML.replace('2026', currentYear);
}
