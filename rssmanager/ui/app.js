document.addEventListener('DOMContentLoaded', fetchItems);

function fetchItems() {
  document.getElementById('loader').style.display = 'block';
  fetch('rss')
    .then(res => res.json())
    .then(data => {
      document.getElementById('loader').style.display = 'none';
      renderItems(data.feed_items);
    });
}

function updateFeeds() {
  fetch('rss/update', { method: 'POST' })
    .then(() => fetchItems());
}

function renderItems(items) {
  const container = document.getElementById('items-container');
  container.innerHTML = '';
  if (items.length === 0) {
    container.innerHTML = '<p>No items available.</p>';
    return;
  }
  items.forEach(item => {
    const card = document.createElement('div');
    card.className = 'card rss-item-card';
    card.setAttribute('data-id', item.id);
    card.innerHTML = `
      <div class="card-content">
        <span class="card-title">${item.title}</span>
        <p><strong>Feed:</strong> ${item.feed}</p>
        <p><a href="${item.link}" target="_blank">Magnet/Link</a></p>
        <div class="actions">
          <button class="btn green" onclick="sendItem('${item.id}')">Add</button>
          <button class="btn red" onclick="hideItem('${item.id}')">Ignore</button>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

function showErrorOnItem(id, message) {
  const card = document.querySelector(`.card[data-id="${id}"]`);
  if (!card) return;

  let errorDiv = card.querySelector('.error-message');
  if (!errorDiv) {
    errorDiv = document.createElement('div');
    errorDiv.className = 'error-message red-text';
    card.querySelector('.card-content').appendChild(errorDiv);
  }
  errorDiv.textContent = `Error: ${message}`;
}

function sendItem(id) {
  fetch(`rss/send/${id}`, { method: 'POST' })
    .then(async (res) => {
      if (!res.ok) {
        const errText = await res.text();
        showErrorOnItem(id, errText || 'Unknown error');
        return;
      }
      fetchItems(); // success
    })
    .catch(err => {
      showErrorOnItem(id, err.message || 'Request failed');
    });
}

function hideItem(id) {
  fetch(`rss/hide/${id}`, { method: 'POST' }).then(() => fetchItems());
}
