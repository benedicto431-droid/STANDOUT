(() => {
  'use strict';

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

  // --- Navigation Toggle ---
  const navToggle = document.querySelector('.nav-toggle');
  const nav = document.querySelector('#site-nav');
  if (navToggle && nav) {
    navToggle.addEventListener('click', () => {
      const open = navToggle.getAttribute('aria-expanded') !== 'true';
      navToggle.setAttribute('aria-expanded', String(open));
      navToggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
      nav.classList.toggle('open', open);
    });
    nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
      nav.classList.remove('open');
      navToggle.setAttribute('aria-expanded', 'false');
      navToggle.setAttribute('aria-label', 'Open navigation');
    }));
  }

  // --- Hero Image Slider ---
  const slides = document.querySelectorAll('.hero-slide');
  const dots = document.querySelectorAll('.hero-slider-dots .dot');
  let currentSlide = 0;
  let slideInterval;

  function showSlide(index) {
    if (!slides.length) return;
    slides.forEach((slide, i) => slide.classList.toggle('active', i === index));
    dots.forEach((dot, i) => dot.classList.toggle('active', i === index));
    currentSlide = index;
  }

  function nextSlide() {
    showSlide((currentSlide + 1) % slides.length);
  }

  function startSlider() {
    if (slides.length > 1) {
      slideInterval = setInterval(nextSlide, 4000);
    }
  }

  if (dots.length > 0) {
    dots.forEach((dot, index) => {
      dot.addEventListener('click', () => {
        clearInterval(slideInterval);
        showSlide(index);
        startSlider();
      });
    });
    startSlider();
  }

  // Expose for swipe handler
  window.__setHeroSlide = showSlide;

  // --- Hero Swipe Support ---
  const hero = document.getElementById('hero-slider');
  if (hero) {
    let startX = 0;
    let startY = 0;
    hero.addEventListener('touchstart', (e) => {
      const t = e.touches[0];
      startX = t.clientX;
      startY = t.clientY;
    }, { passive: true });
    hero.addEventListener('touchend', (e) => {
      const t = e.changedTouches[0];
      const dx = t.clientX - startX;
      const dy = t.clientY - startY;
      if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) {
        clearInterval(slideInterval);
        const next = dx < 0
          ? (currentSlide + 1) % slides.length
          : (currentSlide - 1 + slides.length) % slides.length;
        showSlide(next);
        startSlider();
      }
    }, { passive: true });
  }

  // --- Footer Year ---
  const year = document.querySelector('#current-year');
  if (year) year.textContent = new Date().getFullYear();

  // --- Scroll Reveal Animations ---
  const revealItems = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    }), { threshold: 0.12 });
    revealItems.forEach(item => observer.observe(item));
  } else {
    revealItems.forEach(item => item.classList.add('is-visible'));
  }

  // --- Lightbox (zoom, pan, download, prev/next) ---
  const lightbox = document.getElementById('lightbox');
  const stage = document.getElementById('lb-stage');
  const img = document.getElementById('lb-image');
  const counter = document.getElementById('lb-counter');
  const download = document.getElementById('lb-download');
  const btnPrev = document.getElementById('lb-prev');
  const btnNext = document.getElementById('lb-next');
  const btnClose = document.getElementById('lb-close');
  const btnIn = document.getElementById('lb-zoom-in');
  const btnOut = document.getElementById('lb-zoom-out');
  const btnReset = document.getElementById('lb-reset');

  if (lightbox && img) {
    const heroThumbs = [...document.querySelectorAll('.hero-slide')].map(s => s.dataset.full || s.src);
    const galleryThumbs = [...document.querySelectorAll('.gallery-thumb')].map(b => b.dataset.full);
    const allImages = [...new Set([...heroThumbs, ...galleryThumbs])];

    let index = 0;
    let scale = 1;
    let tx = 0, ty = 0;
    let dragging = false;
    let dragStartX = 0, dragStartY = 0;
    let originTx = 0, originTy = 0;

    function applyTransform() {
      img.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    }

    function reset() {
      scale = 1;
      tx = 0;
      ty = 0;
      applyTransform();
    }

    function show(i) {
      if (!allImages.length) return;
      index = (i + allImages.length) % allImages.length;
      img.src = allImages[index];
      download.href = allImages[index];
      const filename = allImages[index].split('/').pop() || 'image';
      download.setAttribute('download', filename);
      counter.textContent = `${index + 1} / ${allImages.length}`;
      reset();
    }

    function open(i) {
      if (!allImages.length) return;
      lightbox.hidden = false;
      document.body.style.overflow = 'hidden';
      show(i);
    }

    function close() {
      lightbox.hidden = true;
      document.body.style.overflow = '';
    }

    // Open from hero slides
    document.querySelectorAll('.hero-slide').forEach((slide, i) => {
      slide.style.cursor = 'zoom-in';
      slide.addEventListener('click', () => open(heroThumbs.indexOf(slide.dataset.full || slide.src)));
    });

    // Open from gallery thumbnails
    document.querySelectorAll('.gallery-thumb').forEach((btn) => {
      const full = btn.dataset.full;
      const i = allImages.indexOf(full);
      btn.addEventListener('click', () => open(i >= 0 ? i : 0));
    });

    btnPrev?.addEventListener('click', () => show(index - 1));
    btnNext?.addEventListener('click', () => show(index + 1));
    btnClose?.addEventListener('click', close);
    btnReset?.addEventListener('click', reset);
    btnIn?.addEventListener('click', () => { scale = Math.min(scale + 0.25, 5); applyTransform(); });
    btnOut?.addEventListener('click', () => { scale = Math.max(scale - 0.25, 0.5); applyTransform(); });

    document.addEventListener('keydown', (e) => {
      if (lightbox.hidden) return;
      if (e.key === 'Escape') close();
      if (e.key === 'ArrowLeft') show(index - 1);
      if (e.key === 'ArrowRight') show(index + 1);
      if (e.key === '+' || e.key === '=') { scale = Math.min(scale + 0.25, 5); applyTransform(); }
      if (e.key === '-') { scale = Math.max(scale - 0.25, 0.5); applyTransform(); }
    });

    img.addEventListener('mousedown', (e) => {
      if (scale <= 1) return;
      dragging = true;
      dragStartX = e.clientX;
      dragStartY = e.clientY;
      originTx = tx;
      originTy = ty;
      img.style.cursor = 'grabbing';
    });
    window.addEventListener('mousemove', (e) => {
      if (!dragging) return;
      tx = originTx + (e.clientX - dragStartX);
      ty = originTy + (e.clientY - dragStartY);
      applyTransform();
    });
    window.addEventListener('mouseup', () => {
      dragging = false;
      img.style.cursor = scale > 1 ? 'grab' : 'default';
    });

    let pinchStart = 0;
    let pinchScale = 1;
    stage?.addEventListener('touchstart', (e) => {
      if (e.touches.length === 2) {
        pinchStart = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        pinchScale = scale;
      }
    }, { passive: true });
    stage?.addEventListener('touchmove', (e) => {
      if (e.touches.length === 2) {
        const d = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        scale = Math.min(5, Math.max(0.5, pinchScale * (d / pinchStart)));
        applyTransform();
      }
    }, { passive: true });

    stage?.addEventListener('click', (e) => {
      if (e.target === stage) close();
    });
  }

  // --- Chat & Form Variables ---
  const contactForm = document.querySelector('#contact-form');
  const contactStatus = document.querySelector('#contact-status');
  const chatWindow = document.querySelector('#chat-window');
  const chatLauncher = document.querySelector('#chat-launcher');
  const chatForm = document.querySelector('#chat-form');
  const chatMessages = document.querySelector('#chat-messages');
  const chatNotice = document.querySelector('#chat-notice');
  const chatInput = document.querySelector('#chat-input');
  const chatClose = document.querySelector('.chat-close');
  const chatHeading = document.querySelector('.chat-title strong');
  const chatSubheading = document.querySelector('.chat-title small');

  let history = [];
  let conversationToken = null;
  try {
    conversationToken = localStorage.getItem('standout-management-token');
  } catch (_) {
    conversationToken = null;
  }
  let restoreConversationHistory = Boolean(conversationToken);
  let lastMessageId = 0;
  let pollTimer = null;
  let sending = false;

  function setManagementMode() {
    if (chatHeading) chatHeading.textContent = 'Chat with management';
    if (chatSubheading) chatSubheading.textContent = 'Your enquiry goes directly to the team';
  }
  if (conversationToken) setManagementMode();

  function setChatOpen(open) {
    if (!chatWindow || !chatLauncher) return;
    chatWindow.hidden = !open;
    chatLauncher.setAttribute('aria-expanded', String(open));
    chatLauncher.setAttribute('aria-label', open ? 'Close chat' : 'Open chat');
    if (open) chatInput?.focus();
    else chatLauncher.focus();
  }

  chatLauncher?.addEventListener('click', () => setChatOpen(chatWindow.hidden));
  chatClose?.addEventListener('click', () => setChatOpen(false));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && chatWindow && !chatWindow.hidden) setChatOpen(false);
  });

  function addBubble(role, text) {
    if (!chatMessages) return;
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role}`;
    bubble.textContent = text;
    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  async function pollConversation() {
    if (!conversationToken) return;
    try {
      const response = await fetch(`/api/management/conversations/${encodeURIComponent(conversationToken)}?after=${encodeURIComponent(lastMessageId)}`, {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin'
      });
      if (!response.ok) return;
      const data = await response.json();
      (data.messages || []).forEach(message => {
        const id = Number(message.id) || 0;
        if (id > lastMessageId) {
          lastMessageId = id;
          if (message.sender === 'visitor') {
            if (restoreConversationHistory) addBubble('user', message.body || '');
          } else {
            addBubble('assistant', message.body || '');
          }
        }
      });
      restoreConversationHistory = false;
      if (data.status === 'resolved' && chatNotice) {
        chatNotice.textContent = 'This enquiry has been marked resolved. Send a new enquiry through the form to get back in touch.';
      } else if (chatNotice && conversationToken) {
        chatNotice.textContent = 'This chat is connected to your enquiry. Our team can reply here.';
      }
    } catch (_) {
      // Silent
    }
  }

  function startPolling() {
    if (pollTimer) window.clearInterval(pollTimer);
    pollConversation();
    pollTimer = window.setInterval(pollConversation, 12000);
  }

  contactForm?.addEventListener('submit', async event => {
    event.preventDefault();
    if (!contactForm.reportValidity()) return;
    const submit = contactForm.querySelector('button[type="submit"]');
    const payload = Object.fromEntries(new FormData(contactForm).entries());
    contactStatus.textContent = 'Sending your enquiry…';
    contactStatus.className = 'form-status';
    submit.disabled = true;
    try {
      const response = await fetch('/api/management/conversations', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}) },
        body: JSON.stringify(payload)
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || data.message || 'We couldn’t send your enquiry right now. Please try again.');

      conversationToken = data.token;
      setManagementMode();
      try {
        localStorage.setItem('standout-management-token', conversationToken);
      } catch (_) {}
      lastMessageId = 0;
      if (data.messages?.length) {
        data.messages.forEach(message => {
          lastMessageId = Math.max(lastMessageId, Number(message.id) || 0);
          addBubble(message.sender === 'visitor' ? 'user' : 'assistant', message.body || '');
        });
      }
      contactStatus.className = 'form-status success';
      contactStatus.textContent = 'Your enquiry is with our team. We’ll follow up using the contact details you provided.';
      contactForm.reset();

      if (conversationToken) {
        startPolling();
        setChatOpen(true);
        chatNotice.textContent = 'This chat is connected to your enquiry. Our team can reply here.';
        addBubble('assistant', 'Your enquiry has reached the STANDOUT team. You can leave a follow-up message here.');
      }
    } catch (error) {
      contactStatus.className = 'form-status error';
      contactStatus.textContent = error.message || 'Something went wrong. Please try again or call 0731 157 929.';
    } finally {
      submit.disabled = false;
    }
  });

  chatForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const message = chatInput.value.trim();
    if (!message || sending) return;
    sending = true;
    chatInput.value = '';
    chatInput.disabled = true;
    addBubble('user', message);

    if (conversationToken) {
      try {
        const response = await fetch(`/api/management/conversations/${encodeURIComponent(conversationToken)}/messages`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}) },
          body: JSON.stringify({ message })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || data.message || 'That message could not be sent.');
        if (data.message) {
          lastMessageId = Math.max(lastMessageId, Number(data.message.id) || 0);
        }
        if (chatNotice) chatNotice.textContent = 'Sent to the STANDOUT team.';
        pollConversation();
      } catch (error) {
        addBubble('assistant', error.message || 'We couldn’t send that message. Please try again.');
      }
    } else {
      try {
        const response = await fetch('/api/ai-chat', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}) },
          body: JSON.stringify({ message, history: history.slice(-12) })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || data.message || 'The assistant is unavailable right now.');
        const reply = data.reply || 'I can help with general questions. For a detailed project enquiry, please send us a message using the form.';
        history.push({ role: 'user', content: message });
        history.push({ role: 'assistant', content: reply });
        addBubble('assistant', reply);
        if (chatNotice) chatNotice.textContent = '';
      } catch (error) {
        addBubble('assistant', error.message || 'I’m having trouble connecting. Please try again or use the enquiry form.');
      }
    }
    sending = false;
    chatInput.disabled = false;
    chatInput.focus();
  });

  if (conversationToken) startPolling();
})();
