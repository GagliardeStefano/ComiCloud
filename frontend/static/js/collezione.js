// Search functionality
const searchInput = document.getElementById('searchInput');
const comicCardsContainer = document.querySelector('.comics-grid'); // Container for delegation
const comicCount = document.getElementById('comicCount');
const detailModal = document.getElementById('detailModal');
const modalBody = document.getElementById('modalBody');
const closeModalBtn = document.querySelector('.close');

// --- Event Listeners ---

let debounceTimer;

if (searchInput) {
    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value;

        // Usiamo un debounce per non chiamare l'API ad ogni lettera
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            fetchSearchResults(searchTerm);
        }, 300);
    });
}

async function fetchSearchResults(term) {
    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(term)}*`);
        const data = await response.json();

        if (data.results) {
            renderGrid(data.results);
            if (comicCount) comicCount.textContent = data.results.length;
        }
    } catch (error) {
        console.error("Errore ricerca:", error);
    }
}

function renderGrid(comics) {
    comicCardsContainer.innerHTML = ''; // Pulisce la griglia attuale

    if (!comics || comics.length === 0) {
        comicCardsContainer.innerHTML = `
            <div class="empty-state">
                <p>Nessun fumetto trovato per questa ricerca.</p>
            </div>`;
        return;
    }

    // Ricostruisce l'HTML identico a quello di Jinja2
    const html = comics.map(comic => {
        const meta = comic.metadata || {};
        const title = meta.title || 'Titolo Sconosciuto';
        const issue = meta.issue_number || 'N/D';
        const date = meta.publish_date || '';
        const cover = meta.cover_url
            ? `<img src="${meta.cover_url}" alt="Cover" class="comic-cover">`
            : `<div class="comic-cover-placeholder">📖</div>`;

        return `
        <div class="comic-card" id="card-${comic.id}" data-comic-id="${comic.id}">
            ${cover}
            <div class="comic-info">
                <h3>${title}</h3>
                <p class="comic-issue">#${issue}</p>
                <p class="comic-date">${date}</p>
            </div>
        </div>`;
    }).join('');

    comicCardsContainer.innerHTML = html;
}

// Event Delegation for Comic Cards
if (comicCardsContainer) {
    comicCardsContainer.addEventListener('click', (e) => {
        const card = e.target.closest('.comic-card');
        if (card) {
            const comicId = card.dataset.comicId;
            if (comicId) showDetails(comicId);
        }
    });
}

// Close Modal Events
if (closeModalBtn) {
    closeModalBtn.addEventListener('click', closeModal);
}

window.addEventListener('click', (event) => {
    if (event.target === detailModal) {
        closeModal();
    }
});

// Event Delegation for Modal Actions (e.g. Delete Button)
if (modalBody) {
    modalBody.addEventListener('click', (e) => {
        if (e.target.matches('.btn-delete-comic')) {
            const comicId = e.target.dataset.comicId;
            if (comicId) deleteComicFromModal(comicId);
        }
    });
}


// --- Functions ---

async function showDetails(comicId) {
    try {
        const response = await fetch(`/api/comic/${comicId}`);
        const comic = await response.json();

        // Helper per creare liste da array
        const renderList = (items, emptyText = 'N/D') => {
            if (!items || items.length === 0) return `<span class="text-muted">${emptyText}</span>`;
            return items.map(item => `<span class="badge-secondary">${item}</span>`).join(' ');
        };

        modalBody.innerHTML = `
        <div class="detail-container-fixed">
            <div class="detail-image-col">
                 ${comic.metadata && comic.metadata.cover_url ?
                `<img src="${comic.metadata.cover_url}" alt="Cover" class="detail-cover-fixed">` :
                '<div class="detail-cover-placeholder-fixed">📖</div>'
            }
            </div>
            
            <div class="detail-info-scrollable">
                <h2 class="detail-title">${comic.metadata?.title || 'Titolo Sconosciuto'}</h2>
                
                <div class="detail-badges">
                    <span class="badge-primary">#${comic.metadata?.issue_number || 'N/D'}</span>
                    ${comic.metadata?.publisher ? `<span class="badge-publisher">${comic.metadata.publisher}</span>` : ''}
                </div>

                <div class="detail-section">
                    <h3>ℹ️ Informazioni</h3>
                    <p><strong>Pubblicazione:</strong> ${comic.metadata?.publish_date || 'N/D'}</p>
                    ${comic.metadata?.store_date ? `<p><strong>Uscita in edicola:</strong> ${comic.metadata.store_date}</p>` : ''}
                    ${comic.metadata?.cover_price ? `<p><strong>Prezzo copertina:</strong> ${comic.metadata.cover_price}</p>` : ''}
                </div>

                ${comic.metadata?.writers && comic.metadata.writers.length > 0 ? `
                <div class="detail-section">
                    <h3>🖋️ Scrittori</h3>
                    ${renderList(comic.metadata.writers)}
                </div>` : ''}

                ${comic.metadata?.artists && comic.metadata.artists.length > 0 ? `
                <div class="detail-section">
                    <h3>🖼️ Artisti</h3>
                    ${renderList(comic.metadata.artists)}
                </div>` : ''}

                ${comic.metadata?.characters && comic.metadata.characters.length > 0 ? `
                <div class="detail-section">
                    <h3>🦸 Personaggi</h3>
                    ${renderList(comic.metadata.characters)}
                </div>` : ''}

                ${comic.metadata?.teams && comic.metadata.teams.length > 0 ? `
                <div class="detail-section">
                    <h3>👥 Team</h3>
                    ${renderList(comic.metadata.teams)}
                </div>` : ''}

                ${comic.metadata?.story_arcs && comic.metadata.story_arcs.length > 0 ? `
                <div class="detail-section">
                    <h3>📖 Story Arc</h3>
                    ${renderList(comic.metadata.story_arcs)}
                </div>` : ''}

                ${comic.metadata?.plot ?
                `<div class="detail-section">
                        <h3>📝 Trama</h3>
                        <div class="plot-text">${comic.metadata.plot}</div>
                    </div>` :
                ''
            }
                
                 ${comic.metadata?.comic_vine_url ?
                `<a href="${comic.metadata.comic_vine_url}" target="_blank" class="btn-secondary btn-full">🔗 Vedi su Comic Vine</a>` :
                ''
            }
               
                <button class="btn-danger btn-full btn-delete-comic" style="margin-top: 1rem;" data-comic-id="${comicId}">🗑️ Elimina Fumetto</button>
            </div>
        </div>
        `;

        detailModal.classList.remove('hidden');
    } catch (error) {
        alert('Errore caricamento dettagli: ' + error.message);
    }
}

function closeModal() {
    detailModal.classList.add('hidden');
}

async function deleteComicFromModal(comicId) {
    if (!confirm('Sei sicuro di voler eliminare questo fumetto definitivamente?')) return;

    try {
        const res = await fetch(`/api/delete_comic/${comicId}`, { method: 'DELETE' });
        const data = await res.json();

        if (data.success) {
            // Chiudi modale
            closeModal();

            // Rimuovi l'elemento dalla griglia usando l'ID
            const card = document.getElementById(`card-${comicId}`);
            if (card) {
                card.remove();
                // Aggiorna contatore
                if (comicCount) {
                    const currentCount = parseInt(comicCount.textContent);
                    comicCount.textContent = Math.max(0, currentCount - 1);
                }
            } else {
                // Fallback se non trova la card (es. ricarica pagina)
                window.location.reload();
            }

        } else {
            alert('Errore: ' + data.error);
        }
    } catch (error) {
        console.error(error);
        alert('Errore di eliminazione');
    }
}
