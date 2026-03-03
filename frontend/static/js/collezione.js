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

    let deletedComics = JSON.parse(sessionStorage.getItem('deletedComics') || '[]');

    // Filtra via i fumetti che sappiamo essere in fase di eliminazione
    const comicsToShow = comics.filter(c => !deletedComics.includes(c.id));

    if (!comicsToShow || comicsToShow.length === 0) {
        comicCardsContainer.innerHTML = `
            <div class="empty-state">
                <p>Nessun fumetto trovato per questa ricerca.</p>
            </div>`;
        return;
    }

    // Ricostruisce l'HTML identico a quello di Jinja2
    const html = comicsToShow.map(comic => {
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

        const renderCreativeRole = (title, items) => {
            if (!items || items.length === 0 || (items.length === 1 && items[0] === 'N/D')) return '';
            return `
            <div class="role-group">
                <h4>${title}</h4>
                <div>${renderList(items)}</div>
            </div>`;
        };

        // Rimuove N/D dagli array nel caso siano stati salvati
        const cleanArray = (arr) => {
            if (!arr) return [];
            const filtered = arr.filter(i => i !== 'N/D' && i !== '');
            return filtered.length > 0 ? filtered : [];
        };

        const w = cleanArray(comic.metadata?.writers);
        const a = cleanArray(comic.metadata?.artists);
        const col = cleanArray(comic.metadata?.colorists);
        const lett = cleanArray(comic.metadata?.letterers);
        const ed = cleanArray(comic.metadata?.editors);
        const cov = cleanArray(comic.metadata?.cover_artists);

        const char = cleanArray(comic.metadata?.characters);
        const teams = cleanArray(comic.metadata?.teams);
        const loc = cleanArray(comic.metadata?.locations);
        const genres = cleanArray(comic.metadata?.genres);
        const hasCreative = w.length || a.length || col.length || lett.length || ed.length || cov.length;
        const hasUniverse = char.length || teams.length || loc.length;

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
                    <span class="badge-primary">#${comic.metadata?.issue_number && comic.metadata.issue_number !== 'N/D' ? comic.metadata.issue_number : 'N/D'}</span>
                    ${comic.metadata?.publisher && comic.metadata.publisher !== 'N/D' ? `<span class="badge-publisher">${comic.metadata.publisher}</span>` : ''}
                    ${comic.metadata?.format_type && comic.metadata.format_type !== 'N/D' ? `<span class="badge-format">${comic.metadata.format_type}</span>` : ''}
                    ${comic.metadata?.rating && comic.metadata.rating !== 'N/D' ? `<span class="badge-rating">${comic.metadata.rating}</span>` : ''}
                </div>

                ${genres.length > 0 ? `
                <div class="detail-genres">
                    ${genres.map(g => `<span class="badge-genre">${g}</span>`).join('')}
                </div>
                ` : ''}

                <div class="detail-section">
                    <h3>ℹ️ Dettagli Pubblicazione</h3>
                    <div class="publish-info-grid">
                        <div><strong>Data:</strong> ${comic.metadata?.publish_date && comic.metadata.publish_date !== 'N/D' ? comic.metadata.publish_date : 'N/D'}</div>
                    </div>
                    ${comic.metadata?.original_us_info && comic.metadata.original_us_info.title !== 'N/D' ? `
                    <div class="original-us-info">
                        <strong>Edizione Originale (USA):</strong> ${comic.metadata.original_us_info.title} 
                        (${comic.metadata.original_us_info.publisher || 'N/D'}, ${comic.metadata.original_us_info.year || 'N/D'})
                    </div>
                    ` : ''}
                </div>

                ${comic.metadata?.plot && comic.metadata.plot !== 'N/D' ?
                `<div class="detail-section">
                        <h3>📝 Trama</h3>
                        <div class="plot-text">${comic.metadata.plot}</div>
                    </div>` :
                ''
            }
                
                ${hasCreative ? `
                <div class="detail-section">
                    <h3>🎨 Team Creativo</h3>
                    <div class="creative-grid">
                        ${renderCreativeRole('Scrittori', w)}
                        ${renderCreativeRole('Artisti', a)}
                        ${renderCreativeRole('Coloristi', col)}
                        ${renderCreativeRole('Letteristi', lett)}
                        ${renderCreativeRole('Editor', ed)}
                        ${renderCreativeRole('Copertinisti', cov)}
                    </div>
                </div>` : ''}

                ${hasUniverse ? `
                <div class="detail-section">
                    <h3>🌍 Universo e Personaggi</h3>
                    <div class="universe-grid">
                        ${renderCreativeRole('Personaggi', char)}
                        ${renderCreativeRole('Team', teams)}
                        ${renderCreativeRole('Luoghi', loc)}
                    </div>
                </div>` : ''}

               
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
            // Salva l'ID nei fumetti eliminati di recente
            let deletedComics = JSON.parse(sessionStorage.getItem('deletedComics') || '[]');
            deletedComics.push(comicId);
            sessionStorage.setItem('deletedComics', JSON.stringify(deletedComics));

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
