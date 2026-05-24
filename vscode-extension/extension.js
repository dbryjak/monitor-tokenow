// =============================================================
// extension.js — Monitor Tokenów Anthropic (pasek statusu)
// =============================================================
// ZASADA DZIAŁANIA:
//   Python zapisuje dane do dzisiaj.json po każdym wywołaniu API.
//   To rozszerzenie czyta ten plik co N sekund i pokazuje wynik
//   na pasku statusu na dole ekranu VS Code.
//
// KOLORY:
//   brak tła  = zielony (< 80% budżetu)
//   żółty     = ostrzeżenie (80–95%)
//   czerwony  = alarm (> 95%)
// =============================================================

const vscode = require('vscode');
const fs = require('fs');

let statusBarItem;
let odswiezTimer;

// =============================================================
// Aktywacja rozszerzenia (odpala się przy starcie VS Code)
// =============================================================
function activate(context) {
    // Utwórz element na pasku statusu (prawa strona, priorytet 100)
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'monitorTokenow.pokazSzczegoly';
    context.subscriptions.push(statusBarItem);

    // Zarejestruj komendę wywoływaną przez kliknięcie na pasek
    context.subscriptions.push(
        vscode.commands.registerCommand('monitorTokenow.pokazSzczegoly', pokazSzczegoly)
    );

    // Pokaż pasek i od razu wczytaj dane
    statusBarItem.show();
    odswiezDane();

    // Ustaw timer odświeżania (pobiera interwał z ustawień)
    const interwal = pobierzUstawienie('czestotliwoscSekund', 60) * 1000;
    odswiezTimer = setInterval(odswiezDane, interwal);

    // Wyczyść timer gdy rozszerzenie jest dezaktywowane
    context.subscriptions.push({ dispose: () => clearInterval(odswiezTimer) });
}

// =============================================================
// Odczyt danych z pliku i aktualizacja paska statusu
// =============================================================
function odswiezDane() {
    const sciezkaPliku = pobierzUstawienie(
        'sciezkaDzisiaj',
        'D:\\MOJE PROJEKTY\\Monitor-Tokenow\\data\\dzisiaj.json'
    );

    try {
        // Plik nie istnieje — brak wywołań API dzisiaj
        if (!fs.existsSync(sciezkaPliku)) {
            ustawPasek('$(circle-slash) Tokeny: brak danych', undefined,
                'Monitor Tokenów: uruchom monitor_api.py żeby zacząć śledzenie');
            return;
        }

        const dane = JSON.parse(fs.readFileSync(sciezkaPliku, 'utf8'));
        const dzisiaj = new Date().toISOString().split('T')[0];

        // Plik z poprzedniego dnia — jeszcze nie ma dzisiejszych danych
        if (dane.data !== dzisiaj) {
            ustawPasek('$(circle-slash) Tokeny: brak danych', undefined,
                'Brak wywołań API Anthropic dzisiaj');
            return;
        }

        const limit = pobierzUstawienie('limitDzienny', 10.00);
        const procent = limit > 0 ? dane.koszt_usd / limit : 0;

        const tokenyStr = formatujLiczbe(dane.laczne_tokeny);
        const kosztStr = '$' + dane.koszt_usd.toFixed(4);
        const limitStr = '$' + limit.toFixed(2);
        const procentStr = (procent * 100).toFixed(1) + '%';

        // Tooltip z pełnymi detalami (pojawia się po najechaniu)
        const tooltip = [
            `Anthropic API — ${dane.data}`,
            `─────────────────────────`,
            `Wywołania:       ${dane.liczba_wywolan}`,
            `Tokeny wejście:  ${formatujLiczbe(dane.tokeny_wejscia)}`,
            `Tokeny wyjście:  ${formatujLiczbe(dane.tokeny_wyjscia)}`,
            `Tokeny łącznie:  ${tokenyStr}`,
            `Koszt:           ${dane.koszt_usd.toFixed(6)} USD`,
            `Budżet:          ${procentStr} z ${limitStr}`,
            `─────────────────────────`,
            `Kliknij, żeby zobaczyć szczegóły`
        ].join('\n');

        // Dobierz kolor i ikonę do procentu zużycia
        if (procent >= 0.95) {
            ustawPasek(
                `$(error) ${tokenyStr} tok | ${kosztStr} / ${limitStr}`,
                new vscode.ThemeColor('statusBarItem.errorBackground'),
                tooltip
            );
        } else if (procent >= 0.80) {
            ustawPasek(
                `$(warning) ${tokenyStr} tok | ${kosztStr} / ${limitStr}`,
                new vscode.ThemeColor('statusBarItem.warningBackground'),
                tooltip
            );
        } else {
            ustawPasek(
                `$(check) ${tokenyStr} tok | ${kosztStr} / ${limitStr}`,
                undefined,
                tooltip
            );
        }

    } catch (blad) {
        ustawPasek('$(error) Monitor: błąd odczytu', undefined,
            `Błąd: ${blad.message}\nSprawdź ścieżkę w ustawieniach rozszerzenia.`);
    }
}

// =============================================================
// Okno z detalami po kliknięciu na pasek
// =============================================================
function pokazSzczegoly() {
    const sciezkaPliku = pobierzUstawienie(
        'sciezkaDzisiaj',
        'D:\\MOJE PROJEKTY\\Monitor-Tokenow\\data\\dzisiaj.json'
    );

    try {
        if (!fs.existsSync(sciezkaPliku)) {
            vscode.window.showInformationMessage(
                'Monitor Tokenów: Brak danych — uruchom monitor_api.py'
            );
            return;
        }

        const dane = JSON.parse(fs.readFileSync(sciezkaPliku, 'utf8'));
        const limit = pobierzUstawienie('limitDzienny', 10.00);
        const procent = (dane.koszt_usd / limit * 100).toFixed(1);

        vscode.window.showInformationMessage(
            `📊 ${dane.data}  |  ${dane.liczba_wywolan} wywołań  |  ` +
            `${formatujLiczbe(dane.laczne_tokeny)} tokenów  |  ` +
            `$${dane.koszt_usd.toFixed(6)}  (${procent}% budżetu)`
        );
    } catch (blad) {
        vscode.window.showErrorMessage(`Monitor Tokenów: błąd — ${blad.message}`);
    }
}

// =============================================================
// Pomocnicze funkcje
// =============================================================

function ustawPasek(tekst, kolor, tooltip) {
    statusBarItem.text = tekst;
    statusBarItem.backgroundColor = kolor;
    statusBarItem.tooltip = tooltip;
}

function pobierzUstawienie(klucz, domyslna) {
    return vscode.workspace.getConfiguration('monitorTokenow').get(klucz, domyslna);
}

function formatujLiczbe(n) {
    // Formatuje liczbę z separatorem tysięcy np. 1234 -> "1 234"
    return n.toLocaleString('pl-PL');
}

function deactivate() {
    if (odswiezTimer) clearInterval(odswiezTimer);
}

module.exports = { activate, deactivate };
