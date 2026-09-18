document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('menuToggle');
    const sidebar = document.getElementById('sidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
    }
});

async function toggleTask(id) {
    try {
        const res = await fetch(`/tasks/${id}/toggle`, { method: 'POST' });
        if (res.ok) location.reload();
    } catch (e) { console.error(e); }
}

async function toggleHabit(id) {
    try {
        const res = await fetch(`/habits/${id}/toggle`, { method: 'POST' });
        if (res.ok) location.reload();
    } catch (e) { console.error(e); }
}
