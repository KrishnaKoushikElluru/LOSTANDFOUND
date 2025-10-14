// LostNFound - Main JavaScript
const API_ROOT = "https://lostnfound-backend.loca.lt";

// Theme Management
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('themeIcon');
    if (icon) {
        icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    }
}

// Loading Management
function showLoading() {
    document.getElementById('loadingIndicator').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loadingIndicator').style.display = 'none';
}

// Backend Status Check
async function setBackendStatus() {
    try {
        const response = await fetch(`${API_ROOT}/health`);
        if (!response.ok) throw new Error('Backend not responding');
        const data = await response.json();
        document.getElementById('backendStatus').textContent = data.status || 'online';
        document.getElementById('statusDot').classList.remove('offline');
    } catch (error) {
        document.getElementById('backendStatus').textContent = 'offline';
        document.getElementById('statusDot').classList.add('offline');
    }
}

// File Upload UI Updates
function setupFileUploads() {
    // Search image upload
    const searchFileInput = document.getElementById('imageFileSearch');
    const searchUploadArea = document.getElementById('searchUploadArea');
    const searchFileName = document.getElementById('searchFileName');

    searchFileInput.addEventListener('change', function (e) {
        const fileName = e.target.files[0]?.name || 'Click or drag image here';
        searchFileName.textContent = fileName;
        searchFileName.style.color = 'var(--accent-blue)';
    });

    // Drag and drop for search
    searchUploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        searchUploadArea.classList.add('dragover');
    });

    searchUploadArea.addEventListener('dragleave', () => {
        searchUploadArea.classList.remove('dragover');
    });

    searchUploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        searchUploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            searchFileInput.files = files;
            searchFileName.textContent = files[0].name;
            searchFileName.style.color = 'var(--accent-blue)';
        }
    });

    // Upload image
    const uploadFileInput = document.getElementById('imageFile');
    const uploadArea = document.getElementById('uploadArea');
    const uploadFileName = document.getElementById('uploadFileName');

    uploadFileInput.addEventListener('change', function (e) {
        const fileName = e.target.files[0]?.name || 'Click or drag photo here';
        uploadFileName.textContent = fileName;
        uploadFileName.style.color = 'var(--accent-green)';
    });

    // Drag and drop for upload
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            uploadFileInput.files = files;
            uploadFileName.textContent = files[0].name;
            uploadFileName.style.color = 'var(--accent-green)';
        }
    });
}

// Results Management
function clearResults() {
    document.getElementById('results').innerHTML = '';
    document.getElementById('resultsSection').style.display = 'none';
}

function _buildImageUrlFromMeta(meta) {
    if (!meta) return null;
    let path = meta.path || meta.image_path || meta.filename;
    if (!path) return null;
    path = String(path).replace(/\\/g, '/');

    if (path.indexOf('/data/') >= 0) {
        const rel = path.split('/data/').slice(1).join('/data/');
        return `${API_ROOT}/images/${rel}`;
    }

    if (path.startsWith('uploads/') || path.startsWith('/uploads/')) {
        const fname = path.split('/').pop();
        return `${API_ROOT}/uploads/${fname}`;
    }

    if (meta.filename) {
        return `${API_ROOT}/uploads/${meta.filename}`;
    }

    return null;
}

function escapeHtml(text) {
    if (!text && text !== 0) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
        '/': '&#x2F;'
    };
    return String(text).replace(/[&<>"'\/]/g, (char) => map[char]);
}

function renderResults(responseJson) {
    clearResults();
    const resultsContainer = document.getElementById('results');
    const results = responseJson.results || responseJson || [];

    document.getElementById('resultsSection').style.display = 'block';

    if (!results || results.length === 0) {
        resultsContainer.innerHTML = `
      <div class="empty-state" style="grid-column: 1 / -1;">
        <div class="empty-icon">🤷</div>
        <h3 class="empty-title">No results found</h3>
        <p class="empty-message">Try adjusting your search terms or upload a different image</p>
      </div>
    `;
        return;
    }

    results.forEach((result, index) => {
        const card = document.createElement('div');
        card.className = 'result-card';
        card.style.animationDelay = `${index * 0.1}s`;
        card.classList.add('fade-in');

        const meta = result.metadata || result.meta || result || {};
        const imgSrc = result.image_url || _buildImageUrlFromMeta(meta) || '';

        const table = meta.table || result.collection || meta._table || meta.status || '';
        const isLost = String(table).toLowerCase().includes('lost');
        const badgeClass = isLost ? 'badge-lost' : 'badge-found';
        const badgeText = isLost ? '❌ Lost' : '✅ Found';

        const itemName = meta.item_name || meta.filename || result.filename || result.id || 'Unknown Item';
        const location = meta.location || meta.where || 'Unknown Location';
        let ownerName = meta.owner_name || meta.finder_name || 'Unknown';
        let ownerEmail = meta.email || '';

        const score = result.score !== undefined && result.score !== null
            ? (Number(result.score) * 100).toFixed(1)
            : null;

        const imagePlaceholder = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='300'%3E%3Crect fill='%23374151' width='400' height='300'/%3E%3Ctext fill='%239ca3af' font-family='Arial' font-size='18' x='50%25' y='50%25' text-anchor='middle' dy='.3em'%3ENo Image%3C/text%3E%3C/svg%3E`;

        card.innerHTML = `
      <div class="card-image-container">
        ${imgSrc ? `
          <img 
            src="${imgSrc}" 
            alt="${escapeHtml(itemName)}" 
            class="card-image"
            onerror="this.src='${imagePlaceholder}'"
          />
        ` : `
          <div class="card-image" style="display: flex; align-items: center; justify-content: center; background: var(--bg-secondary);">
            <i class="fas fa-image" style="font-size: 4rem; color: var(--text-muted);"></i>
          </div>
        `}
        <div class="badge ${badgeClass}">${badgeText}</div>
        ${score ? `
          <div class="match-score">
            <i class="fas fa-bullseye"></i> ${score}% match
          </div>
        ` : ''}
      </div>
      
      <div class="card-content">
        <h3 class="card-title" title="${escapeHtml(itemName)}">
          ${escapeHtml(itemName)}
        </h3>
        
        <div class="card-detail">
          <i class="fas fa-map-marker-alt card-detail-icon" style="color: var(--accent-blue);"></i>
          <span>${escapeHtml(location)}</span>
        </div>
        
        <div class="card-detail">
          <i class="fas fa-user card-detail-icon" style="color: var(--accent-purple);"></i>
          <span>${escapeHtml(ownerName)}${ownerEmail ? ` (${escapeHtml(ownerEmail)})` : ''}</span>
        </div>
        
        ${meta.description ? `
          <div class="card-detail">
            <i class="fas fa-align-left card-detail-icon" style="color: var(--accent-green);"></i>
            <span class="card-description">${escapeHtml(meta.description)}</span>
          </div>
        ` : ''}
      </div>
    `;

        resultsContainer.appendChild(card);
    });

    // Smooth scroll to results
    setTimeout(() => {
        document.getElementById('resultsSection').scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }, 100);
}

// Search Functions
async function searchByText() {
    const query = document.getElementById('textQuery').value.trim();
    if (!query) {
        alert('⚠️ Please enter a search term first.');
        return;
    }

    showLoading();
    try {
        const formData = new URLSearchParams();
        formData.append('text', query);
        formData.append('k', '12');

        const response = await fetch(`${API_ROOT}/search/text`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData.toString()
        });

        if (!response.ok) {
            const text = await response.text();
            throw new Error(text);
        }

        const data = await response.json();
        renderResults(data);
    } catch (error) {
        alert(`❌ Error: ${error.message}`);
    } finally {
        hideLoading();
    }
}

async function searchByImage() {
    const fileInput = document.getElementById('imageFileSearch');
    const file = fileInput.files[0];

    if (!file) {
        alert('⚠️ Please select an image file first.');
        return;
    }

    showLoading();
    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('k', '12');

        const response = await fetch(`${API_ROOT}/search/image`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const text = await response.text();
            throw new Error(text);
        }

        const data = await response.json();
        renderResults(data);
    } catch (error) {
        alert(`❌ Error: ${error.message}`);
    } finally {
        hideLoading();
    }
}

async function uploadAndIndex() {
    const fileInput = document.getElementById('imageFile');
    const file = fileInput.files[0];

    if (!file) {
        alert('⚠️ Please select an image file first.');
        return;
    }

    const formData = new FormData();
    formData.append('status', document.getElementById('status').value || '');
    formData.append('item_name', document.getElementById('itemName').value || '');
    formData.append('location', document.getElementById('location').value || '');
    formData.append('owner_name', document.getElementById('ownerName').value || '');
    formData.append('email', document.getElementById('ownerEmail').value || '');
    formData.append('description', document.getElementById('description').value || '');
    formData.append('file', file);

    showLoading();

    try {
        let response = await fetch(`${API_ROOT}/index/item`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            response = await fetch(`${API_ROOT}/index/image`, {
                method: 'POST',
                body: formData
            });
        }

        if (!response.ok) {
            const text = await response.text();
            throw new Error(text);
        }

        const data = await response.json();

        alert('✅ Item successfully indexed! You can now search for it.');

        // Clear form
        document.getElementById('indexForm').reset();
        document.getElementById('uploadFileName').textContent = 'Click or drag photo here';
        document.getElementById('uploadFileName').style.color = '';

        // Try to show the uploaded item
        if (data && data.results) {
            renderResults(data);
        } else if (Array.isArray(data)) {
            renderResults({ results: data });
        } else {
            // Search for the uploaded image
            const searchFormData = new FormData();
            searchFormData.append('file', file);
            const searchResponse = await fetch(`${API_ROOT}/search/image`, {
                method: 'POST',
                body: searchFormData
            });

            if (searchResponse.ok) {
                const searchData = await searchResponse.json();
                renderResults(searchData);
            }
        }
    } catch (error) {
        alert(`❌ Upload failed: ${error.message}`);
    } finally {
        hideLoading();
    }
}

// Event Listeners
function setupEventListeners() {
    document.getElementById('themeToggle').addEventListener('click', toggleTheme);
    document.getElementById('btnTextSearch').addEventListener('click', searchByText);
    document.getElementById('btnImageSearch').addEventListener('click', searchByImage);
    document.getElementById('btnIndex').addEventListener('click', uploadAndIndex);

    // Enter key for text search
    document.getElementById('textQuery').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            searchByText();
        }
    });
}

// Initialize Particles.js
function initParticles() {
    if (typeof particlesJS !== 'undefined') {
        particlesJS('particles-js', {
            particles: {
                number: { value: 80, density: { enable: true, value_area: 800 } },
                color: { value: ['#00d4ff', '#a855f7', '#10b981'] },
                shape: { type: 'circle' },
                opacity: {
                    value: 0.3,
                    random: true,
                    anim: { enable: true, speed: 1, opacity_min: 0.1, sync: false }
                },
                size: {
                    value: 3,
                    random: true,
                    anim: { enable: true, speed: 2, size_min: 0.1, sync: false }
                },
                line_linked: {
                    enable: true,
                    distance: 150,
                    color: '#00d4ff',
                    opacity: 0.2,
                    width: 1
                },
                move: {
                    enable: true,
                    speed: 1,
                    direction: 'none',
                    random: true,
                    straight: false,
                    out_mode: 'out',
                    bounce: false
                }
            },
            interactivity: {
                detect_on: 'canvas',
                events: {
                    onhover: { enable: true, mode: 'grab' },
                    onclick: { enable: true, mode: 'push' },
                    resize: true
                },
                modes: {
                    grab: { distance: 140, line_linked: { opacity: 0.5 } },
                    push: { particles_nb: 4 }
                }
            },
            retina_detect: true
        });
    }
}

// Initialize AOS
function initAOS() {
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 800,
            once: true,
            offset: 100
        });
    }
}

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    setupFileUploads();
    setupEventListeners();
    setBackendStatus();
    initParticles();
    initAOS();

    // Check backend status every 30 seconds
    setInterval(setBackendStatus, 30000);
});