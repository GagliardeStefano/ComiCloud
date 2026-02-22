const fileInput = document.getElementById('fileInput');
const cameraInput = document.getElementById('cameraInput');
const galleryInput = document.getElementById('galleryInput');
const uploadBox = document.getElementById('uploadBox');
const preview = document.getElementById('preview');
const uploadForm = document.getElementById('uploadForm');
const uploadBtn = document.getElementById('uploadBtn');
const message = document.getElementById('message');

// Funzione per gestire la selezione dei file
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        // Seleziona il file per il form
        window.selectedFile = file;

        const reader = new FileReader();
        reader.onload = (event) => {
            preview.innerHTML = `<img src="${event.target.result}" alt="Preview">`;
            preview.classList.remove('hidden');
            uploadBtn.disabled = false;
        };
        reader.readAsDataURL(file);
    }
}

if (fileInput) fileInput.addEventListener('change', handleFileSelect);
if (cameraInput) cameraInput.addEventListener('change', handleFileSelect);
if (galleryInput) galleryInput.addEventListener('change', handleFileSelect);

// Funzione di Polling: chiede al server se è pronto
let pollingInterval = null; // Globale per poterlo stoppare

function checkAnalysisStatus(blobName) {
    let attempts = 0;
    const maxAttempts = 30; // Timeout dopo 60 secondi

    // Reset intervallo precedente se esiste
    if (pollingInterval) clearInterval(pollingInterval);

    pollingInterval = setInterval(async () => {
        attempts++;

        if (attempts > maxAttempts) {
            clearInterval(pollingInterval);
            message.innerHTML = `⚠️ <b>Timeout.</b> L'analisi sta impiegando più del previsto. <br><a href="/collezione">Vai alla collezione</a> per controllare se appare.`;
            message.className = 'message warning';
            return;
        }

        try {
            const res = await fetch(`/api/check_status?blob_name=${encodeURIComponent(blobName)}`);
            const statusData = await res.json();

            if (statusData.status === 'completed') {
                clearInterval(pollingInterval);
                const title = statusData.comic.metadata.title || "Fumetto Identificato";
                message.innerHTML = `✅ <b>Successo!</b> Trovato: "${title}". <br>Reindirizzamento...`;
                message.className = 'message success';
                setTimeout(() => { window.location.href = '/collezione'; }, 1500);

            } else if (statusData.status === 'error') {
                // ERRORE: L'AI ha fallito
                clearInterval(pollingInterval);

                message.innerHTML = `❌ <b>Analisi Fallita.</b> ${statusData.message || 'Errore sconosciuto'} <br>Prova con un'immagine più chiara.`;
                message.className = 'message error';
                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Riprova Upload';

                // PULIZIA: Eliminiamo il record "error" dal DB per non sporcarlo
                if (statusData.comic && statusData.comic.id) {
                    console.log("Auto-deleting error record:", statusData.comic.id);
                    fetch(`/api/delete_comic/${statusData.comic.id}`, { method: 'DELETE' });
                }
            }

        } catch (error) {
            console.error("Errore polling:", error);
        }
    }, 2000);
}

// Gestione invio form
uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const file = window.selectedFile;
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Caricamento in corso...';
    message.classList.add('hidden');

    try {
        // 1. Upload Immagine
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            // 2. Se l'upload è ok, avvisa l'utente e avvia il polling
            message.textContent = "📤 Immagine caricata. Stiamo analizzando il fumetto...";
            message.className = 'message info'; // Assicurati di avere uno stile .info o usa .success
            message.classList.remove('hidden');

            // Avvia il controllo stato passando il nome del blob
            checkAnalysisStatus(data.blob_name);
        } else {
            throw new Error(data.error || 'Errore upload');
        }
    } catch (error) {
        message.textContent = 'Errore: ' + error.message;
        message.className = 'message error';
        message.classList.remove('hidden');
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Upload';
    }
});
