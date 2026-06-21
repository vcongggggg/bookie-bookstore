/**
 * Bookie — Cinematic 3D Landing Page
 * Inspired by: Hubtown, landing.love
 * Modules: Loader → Three.js Particles → Navbar → GSAP → Tilt → Observers → CTA Particles
 */

document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('home-3d-body');

    initLoader();
    initNavbarScroll();
    initHeroParticles();
    initGSAPAnimations();
    init3DTilt();
    initAIObserver();
    initBentoHover();
    initCTAParticles();
});


/* ══════════════════════════════════════════
   1. LOADING SCREEN
══════════════════════════════════════════ */
function initLoader() {
    const loader = document.getElementById('home-loader');
    if (!loader) return;

    const percentEl = loader.querySelector('.loader-percent');
    let pct = 0;
    const tick = setInterval(() => {
        pct = Math.min(pct + Math.random() * 18, 100);
        if (percentEl) percentEl.textContent = Math.floor(pct) + '%';
        if (pct >= 100) {
            clearInterval(tick);
            setTimeout(() => {
                loader.classList.add('hidden');
                // Trigger hero entrance after loader disappears
                triggerHeroEntrance();
            }, 400);
        }
    }, 90);
}


/* ══════════════════════════════════════════
   2. NAVBAR — Transparent → Dark on Scroll
══════════════════════════════════════════ */
function initNavbarScroll() {
    const navbar = document.querySelector('.navbar-bs');
    if (!navbar) return;

    const onScroll = () => {
        if (window.scrollY > 60) {
            navbar.classList.add('scrolled-nav');
        } else {
            navbar.classList.remove('scrolled-nav');
        }
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
}


/* ══════════════════════════════════════════
   3. THREE.JS — PARTICLE FIELD (No broken book)
   Clean particle cosmos — reliable, beautiful
══════════════════════════════════════════ */
function initHeroParticles() {
    const canvas = document.getElementById('hero-canvas');
    if (!canvas || typeof THREE === 'undefined') return;

    const scene    = new THREE.Scene();
    const camera   = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 100);
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    camera.position.z = 5;

    // ── Layer 1: Gold dust (small, many) ──
    const dustCount = 2000;
    const dustPos = new Float32Array(dustCount * 3);
    const dustSpeeds = new Float32Array(dustCount);
    for (let i = 0; i < dustCount; i++) {
        dustPos[i * 3]     = (Math.random() - 0.5) * 20;
        dustPos[i * 3 + 1] = (Math.random() - 0.5) * 14;
        dustPos[i * 3 + 2] = (Math.random() - 0.5) * 10;
        dustSpeeds[i]      = 0.002 + Math.random() * 0.004;
    }
    const dustGeo = new THREE.BufferGeometry();
    dustGeo.setAttribute('position', new THREE.BufferAttribute(dustPos, 3));
    const dustMat = new THREE.PointsMaterial({
        size: 0.018,
        color: 0xC9A96E,
        transparent: true,
        opacity: 0.55,
        blending: THREE.AdditiveBlending,
        depthWrite: false
    });
    const dustMesh = new THREE.Points(dustGeo, dustMat);
    scene.add(dustMesh);

    // ── Layer 2: Blue-white stars (large, sparse) ──
    const starCount = 300;
    const starPos = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount; i++) {
        starPos[i * 3]     = (Math.random() - 0.5) * 30;
        starPos[i * 3 + 1] = (Math.random() - 0.5) * 20;
        starPos[i * 3 + 2] = (Math.random() - 0.5) * 15 - 2;
    }
    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
    const starMat = new THREE.PointsMaterial({
        size: 0.045,
        color: 0xffffff,
        transparent: true,
        opacity: 0.35,
        blending: THREE.AdditiveBlending,
        depthWrite: false
    });
    const starMesh = new THREE.Points(starGeo, starMat);
    scene.add(starMesh);

    // ── Layer 3: Floating geometric lines (book-page aesthetic) ──
    const linesMat = new THREE.LineBasicMaterial({
        color: 0x4F8EF7,
        transparent: true,
        opacity: 0.06,
        blending: THREE.AdditiveBlending
    });
    const linesGroup = new THREE.Group();
    for (let i = 0; i < 8; i++) {
        const pts = [];
        const startX = (Math.random() - 0.5) * 12;
        const startY = (Math.random() - 0.5) * 8;
        const z = -3 - Math.random() * 3;
        pts.push(new THREE.Vector3(startX, startY, z));
        pts.push(new THREE.Vector3(startX + (Math.random() - 0.5) * 4, startY + (Math.random() - 0.5) * 4, z));
        const geo = new THREE.BufferGeometry().setFromPoints(pts);
        linesGroup.add(new THREE.Line(geo, linesMat));
    }
    scene.add(linesGroup);

    // ── Mouse Parallax ──
    let targetMouseX = 0, targetMouseY = 0;
    let currentMouseX = 0, currentMouseY = 0;
    document.addEventListener('mousemove', (e) => {
        targetMouseX = (e.clientX / window.innerWidth  - 0.5) * 1.5;
        targetMouseY = (e.clientY / window.innerHeight - 0.5) * 1.0;
    }, { passive: true });

    // ── Animation Loop ──
    const clock = new THREE.Clock();
    let animating = true;

    // Stop animation when section scrolled out of view (perf)
    const heroSection = document.getElementById('hero-section');
    const perfObserver = new IntersectionObserver(entries => {
        animating = entries[0].isIntersecting;
    });
    if (heroSection) perfObserver.observe(heroSection);

    function animate() {
        requestAnimationFrame(animate);
        if (!animating) return;

        const t = clock.getElapsedTime();

        // Smooth mouse lerp
        currentMouseX += (targetMouseX - currentMouseX) * 0.04;
        currentMouseY += (targetMouseY - currentMouseY) * 0.04;

        // Dust slow drift + rotation
        dustMesh.rotation.y  = t * 0.015 + currentMouseX * 0.3;
        dustMesh.rotation.x  = currentMouseY * 0.2;

        // Stars gentle wobble
        starMesh.rotation.y  = t * 0.007;
        starMesh.rotation.x  = Math.sin(t * 0.3) * 0.03;

        // Lines slow rotation
        linesGroup.rotation.y = t * 0.01 + currentMouseX * 0.15;

        // Camera subtle drift
        camera.position.x = currentMouseX * 0.6;
        camera.position.y = -currentMouseY * 0.4;
        camera.lookAt(scene.position);

        renderer.render(scene, camera);
    }
    animate();

    // ── Resize ──
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });
}


/* ══════════════════════════════════════════
   4. GSAP SCROLL ANIMATIONS
══════════════════════════════════════════ */
function triggerHeroEntrance() {
    if (typeof gsap === 'undefined') {
        // Fallback: just show them
        document.querySelectorAll('.hero-tag,.hero-headline,.hero-subtext,.hero-btns,.hero-scroll-hint')
            .forEach(el => {
                el.style.opacity = '1';
                el.style.transform = 'none';
            });
        return;
    }

    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });
    tl.to('.hero-tag',        { opacity: 1, y: 0, duration: 0.9 })
      .to('.hero-headline',   { opacity: 1, y: 0, duration: 1.1 }, '-=0.6')
      .to('.hero-subtext',    { opacity: 1, y: 0, duration: 0.9 }, '-=0.7')
      .to('.hero-btns',       { opacity: 1, y: 0, duration: 0.8 }, '-=0.6')
      .to('.hero-scroll-hint',{ opacity: 1, y: 0, duration: 0.6 }, '-=0.4');
}

function initGSAPAnimations() {
    if (typeof gsap === 'undefined' || typeof ScrollTrigger === 'undefined') return;
    gsap.registerPlugin(ScrollTrigger);

    // Section labels + titles
    gsap.utils.toArray('.s-label, .s-title, .s-sub').forEach(el => {
        gsap.from(el, {
            scrollTrigger: { trigger: el, start: 'top 95%' },
            y: 35, opacity: 0, duration: 1, ease: 'power2.out',
            clearProps: 'opacity'
        });
    });

    // Book cards — stagger
    gsap.from('.book-card-3d', {
        scrollTrigger: { trigger: '.book-grid-3d', start: 'top 95%' },
        y: 60, opacity: 0, duration: 0.9,
        stagger: 0.12, ease: 'power2.out',
        clearProps: 'opacity'
    });

    // Bento items
    gsap.from('.bento-item', {
        scrollTrigger: { trigger: '.bento-grid', start: 'top 95%' },
        scale: 0.92, opacity: 0, duration: 0.8,
        stagger: 0.08, ease: 'back.out(1.4)',
        clearProps: 'opacity'
    });

    // Review cards
    gsap.from('.review-card', {
        scrollTrigger: { trigger: '.reviews-grid', start: 'top 95%' },
        y: 40, opacity: 0, duration: 0.8,
        stagger: 0.12, ease: 'power2.out',
        clearProps: 'opacity'
    });

    // CTA
    gsap.from('.cta-headline, .cta-sub, .cta-section .btn-hero-primary', {
        scrollTrigger: { trigger: '.cta-section', start: 'top 95%' },
        y: 40, opacity: 0, duration: 1,
        stagger: 0.15, ease: 'power3.out',
        clearProps: 'opacity'
    });

    // Ticker pause on hover
    document.querySelectorAll('.ticker-track').forEach(track => {
        track.addEventListener('mouseenter', () => track.style.animationPlayState = 'paused');
        track.addEventListener('mouseleave', () => track.style.animationPlayState = 'running');
    });
}


/* ══════════════════════════════════════════
   5. 3D TILT — Book Cards
══════════════════════════════════════════ */
function init3DTilt() {
    document.querySelectorAll('.book-card-3d').forEach(card => {
        let rafId;

        card.addEventListener('mouseenter', () => {
            card.style.transition = 'border-color 0.4s ease, background 0.4s ease';
        });

        card.addEventListener('mousemove', (e) => {
            cancelAnimationFrame(rafId);
            rafId = requestAnimationFrame(() => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const cx = rect.width  / 2;
                const cy = rect.height / 2;
                const rotX = ((y - cy) / cy) * -10;
                const rotY = ((x - cx) / cx) *  10;

                card.style.transform = `perspective(900px) rotateX(${rotX}deg) rotateY(${rotY}deg) scale3d(1.015,1.015,1.015)`;

                const glare = card.querySelector('.card-glare');
                if (glare) {
                    glare.style.background = `radial-gradient(circle at ${x}px ${y}px, rgba(255,255,255,0.1) 0%, transparent 70%)`;
                }
            });
        });

        card.addEventListener('mouseleave', () => {
            cancelAnimationFrame(rafId);
            card.style.transition = 'transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1), border-color 0.4s ease, background 0.4s ease';
            card.style.transform  = 'perspective(900px) rotateX(0deg) rotateY(0deg) scale3d(1,1,1)';
            const glare = card.querySelector('.card-glare');
            if (glare) glare.style.background = '';
        });
    });
}


/* ══════════════════════════════════════════
   6. INTERSECTION OBSERVER — AI Cards
══════════════════════════════════════════ */
function initAIObserver() {
    const cards = document.querySelectorAll('.ai-feature-card');
    if (!cards.length) return;

    const io = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                io.unobserve(entry.target);
            }
        });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });

    cards.forEach(c => io.observe(c));
}


/* ══════════════════════════════════════════
   7. BENTO GRID — Cursor glow tracker
══════════════════════════════════════════ */
function initBentoHover() {
    document.querySelectorAll('.bento-item').forEach(item => {
        item.addEventListener('mousemove', (e) => {
            const rect = item.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            item.style.setProperty('--mouse-x', `${x}px`);
            item.style.setProperty('--mouse-y', `${y}px`);
        });
    });
}


/* ══════════════════════════════════════════
   8. CTA SECTION — Floating Particles
══════════════════════════════════════════ */
function initCTAParticles() {
    const container = document.querySelector('.cta-particles');
    if (!container) return;

    const count = 25;
    for (let i = 0; i < count; i++) {
        const p = document.createElement('div');
        p.className = 'cta-particle';
        p.style.cssText = `
            left: ${Math.random() * 100}%;
            bottom: ${Math.random() * 20}%;
            --dur: ${3 + Math.random() * 5}s;
            --delay: ${Math.random() * 6}s;
            width: ${2 + Math.random() * 3}px;
            height: ${2 + Math.random() * 3}px;
            opacity: ${0.3 + Math.random() * 0.4};
        `;
        container.appendChild(p);
    }
}
