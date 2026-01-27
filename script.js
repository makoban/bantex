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
// Form Submission Handler
// ========================================
const form = document.querySelector('.cta-form');

if (form) {
    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const formData = new FormData(this);
        const data = {};
        formData.forEach((value, key) => {
            data[key] = value;
        });

        // Show success message
        const button = this.querySelector('.submit-button');
        const originalText = button.innerHTML;

        button.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20,6 9,17 4,12"/>
            </svg>
            送信完了しました
        `;
        button.style.background = 'linear-gradient(135deg, #10b981 0%, #059669 100%)';
        button.disabled = true;

        // Reset after 3 seconds
        setTimeout(() => {
            button.innerHTML = originalText;
            button.style.background = '';
            button.disabled = false;
            this.reset();
        }, 3000);

        // Log form data (replace with actual API call)
        console.log('Form submitted:', data);
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
