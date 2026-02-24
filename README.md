# :cloud: Comicloud - La tua libreria di fumetti sul cloud
**Comicloud** è un'applicazione web Cloud-Native sviluppata per gestire collezioni digitali di fumetti. Sfruttando la potenza dell'Intelligenza Artificiale e un'architettura a microservizi (PaaS e Serverless) su Microsoft Azure, l'applicazione permette agli utenti di scattare o caricare una foto della copertina di un fumetto. Il sistema riconoscerà automaticamente l'albo, estraendo metadati complessi (titolo, autori, trama, editori) e salvandoli nel catalogo personale dell'utente.

---

## :sparkles: Funzionalità Principali
* **Riconoscimento AI Automatico**: sfrutta le capacità di Visione di GPT-4o per analizzare la copertina ed estrarre i dati bibliografici (Titolo, Numero, Anno, Trama, Autori, Personaggi).
* **Architettura Asincrona e Disaccoppiata**: l'elaborazione dell'immagine e le operazioni di eliminazione avvengono in background tramite code, garantendo un'interfaccia utente fluida e reattiva.
* **Ricerca Avanzata**: ricerca rapida e tollerante agli errori tra i fumetti della propria collezione tramite Azure AI Search.
* **Autenticazione**: gestione sicura degli utenti tramite Azure Entra ID
* **Design Responsive**: interfaccia web ottimizzata per PC, tablet e smartphone (con supporto per l'accesso diretto alla fotocamera sui dispositivi mobili)

---

## :building_construction: Architettura Cloud e Servizi Azure Utilizzati
Il progetto è stato progettato seguendo i paradigmi del **Cloud Computing** e si appoggia interamente all'ecosistema Microsoft Azure:
1. **Azure App Service (Linux)**: ospita il frontend sviluppato in Python con Flask. Gestisce l'interfaccia utente, le chiamate API REST e l'upload diretto delle immagini
2. **Azure Blob Storage**: storage utilizzato per salvare le immagini delle copertine originali caricate dagli utenti
3. **Azure Service Bus**: message broker che agisce come intermezzo asincrono tra il frontend e il backend, gestendo le code `process-image-queue` e `delete-comic-queue`.
4. **Azure Function (Serverless)**: backend in background basato su trigger del Service Bus. Si occupa dell'orchestrazione per l'estrazione dei metadati e dell'aggiornamento dei database.
5. **Azure OpenAI (GPT-4o)**: fornisce l'intelligenza artificiale generativa e di Computer Vision. Riceve l'URL dell'immagine da analizzare e restituisce un JSON strutturato con metadati del fumetto.
6. **Azure Cosmos DB (NoSQL)**: Database principale. Memorizza i documenti JSON contenenti i metadati dei fumetti e l'ID dell'utente proprietario
7. **Azure AI Search**: motore di ricerca per l'indicizzazione dei dati di Cosmos DB, abilitando ricerche testuali complesse (per titolo, autore, protagonisti, ecc.).
8. **App Service Authentication**: autenticazione dell'utente tramite l'infrastruttura Microsoft Entra ID.

---

## :arrows_counterclockwise: Flusso di Funzionamento
### Inserimento di un nuovo fumetto (Upload & Analisi)
1. L'utente accede all'app e carica la foto del fumetto
2. Il **Frontend** convalida il file e lo carica sul container **Blob Storage**
3. Il caricamento sul Blob genera un evento (via Event Grid) che viene instradato nella coda `process-image-queue` del **Service Bus**
4. Il Frontend risponde all'utente e avvia un _polling_ per attendere il completamento dell'analisi.
5. La coda innesca una **Function**, quest'ultima estrae l'URL dell'immagine, interroga il modello **OpenAI GPT-4o** inviando l'immagine e un prompt, riceve l'output JSON e lo salva nel **Cosmos DB**, aggiorna l'indice di **AI Search**
6. Il Frontend rileva che lo stato del fumetto è completato e reindirizza l'utente alla sua collezione aggiornata

### Eliminazione di un fumetto
1. L'utente clicca su "Elimina"
2. Il frontend verifica la proprietà dell'oggetto e invia un messaggio con l'ID alla coda `delete-comic-queue`
3. Una Function preleva il messaggio ed esegue la pulizia: elimina l'immagine dal Blob Storage, rimuove il record da Cosmos DB e lo rimuove dall'indice di Ai Search.

---

## :file_folder: Struttura del Repository
```
ComiCloud/
├── frontend/                   # Web App (Azure App Service)
│   ├── app.py                  # Entry point Flask
│   ├── Procfile                # Configurazione di avvio per Gunicorn
│   ├── requirements.txt        # Dipendenze Frontend
│   ├── runtime.txt             # Versione Python (3.11)
│   ├── static/                 # CSS e JavaScript 
│   └── templates/              # File HTML (base, home, collezione)
|
├── services/                   # Moduli condivisi per le logiche di business backend
│   ├── blob_service.py         # Interazione con Azure Blob Storage
│   ├── cosmos_service.py       # Operazioni su Cosmos DB
│   ├── search_service.py       # Indicizzazione e query su AI Search
│   └── vision_service.py       # Chiamate API verso Azure OpenAI (GPT-4o)
|
├── function_app.py             # Azure Functions v2 (Trigger per code Service Bus)
├── host.json                   # Configurazione dell'host delle Functions
├── requirements.txt            # Dipendenze per le Azure Functions
└── .funcignore / .gitignore    # File e cartelle escluse dal versionamento/deploy
```

---

## :gear: Configurazione & Variabili d'Ambiente
Sia per il Frontend (App Service) che per le Azure Functions, sono state configurate le seguenti variabili d'ambiente:

**Database & Storage**

`STORAGE_CONNECTION`: connection string della risorsa Azure Storage

`BLOB_CONTAINER_NAME`: nome del container dove caricare le immagini

`COSMOS_CONNECTION`: connection string per Azure Cosmos DB

`COSMOS_DB_NAME`: nome del database in Cosmos

`COSMOS_CONTAINER_NAME`: nome del container in Cosmos

**Service Bus & Code**

`SERVICEBUS_CONNECTION`: connection string di Azure Service Bus

**Azure OpenAI**

`AZURE_OPENAI_ENDPOINT`: endpoint del servizio Azure OpenAI

`AZURE_OPENAI_KEY`: chiave API del servizio OpenAI

**Azure AI Search**

`SEARCH_ENDPOINT`: endpoint del servizio AI Search

`SEARCH_KEY`: chiave di admin per AI Search

`SEARCH_INDEX_NAME`: nome dell'indice creato per interrogare i fumetti nel Cosmos

## :clipboard: Requisiti
* Python 3.11+
* Risorse Azure configurate


