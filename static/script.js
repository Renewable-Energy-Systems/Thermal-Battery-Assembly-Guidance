
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js');
}

const nextBtn = document.getElementById('nextBtn');
const statusP = document.getElementById('status');

async function sendNext() {
    try {
        const res = await fetch('/next', {method: 'POST'});
        if (res.ok) {
            statusP.textContent = 'Step logged at ' + new Date().toLocaleTimeString();
        } else {
            throw new Error('Server error');
        }
    } catch (err) {
        statusP.textContent = 'Error: ' + err.message;
    }
}

nextBtn.addEventListener('click', sendNext);
