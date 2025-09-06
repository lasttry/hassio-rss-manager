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

    const seeders = item.attrs?.seeders || '—';
    const peers = item.attrs?.peers || '—';
    const imdbId = item.attrs?.imdbid;
    const imdbLink = imdbId
      ? `<a href="https://www.imdb.com/title/${imdbId}" class="btn yellow darken-2 btn-small" target="_blank" style="margin-top: 8px;">
           🎬 Open IMDb Page
         </a>`
      : '';

    console.log(item.has_image)
    const coverImage = item.has_image
      ? `<div class="cover-container">
          <img src="rss/poster/${item.id}" alt="Cover Image" class="cover-image">
        </div>`
      : '';

    card.innerHTML = `
      <div class="card-horizontal">
        ${coverImage}
        <div class="card-content">
          <span class="card-title">${item.title}</span>
          <p><strong>Feed:</strong> ${item.feed}</p>
          <p><strong>Seeders:</strong> ${seeders} | <strong>Peers:</strong> ${peers}</p>
          <p><a href="${item.link}" target="_blank">🔗 Magnet/Link</a></p>
          ${item.description ? `<p class="grey-text">${item.description}</p>` : ''}
          ${imdbLink}
        </div>
      </div>
      <div class="card-action right-align">
        <button class="btn green btn-small" onclick="sendItem('${item.id}')">ADD</button>
        <button class="btn red btn-small" onclick="hideItem('${item.id}')">IGNORE</button>
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

function deleteRSS(item) {
  fetch(`rss/${item}`, { method: 'DELETE' })
    .then(async (res) => {
      if (!res.ok) {
        const errText = await res.text();
        showErrorOnItem(id, errText || 'Unknown error');
        return;
      }
      // 🔁 Remove o item visualmente sem recarregar tudo
      const itemElement = document.getElementById(`rss-item-${itemId}`);
      if (itemElement) itemElement.remove();

      // fetchItems(); // success
    })
    .catch(err => {
      showErrorOnItem(id, err.message || 'Request failed');
    });
}

function hideItem(id) {
  fetch(`rss/hide/${id}`, { method: 'POST' }).then(() => fetchItems());
}
