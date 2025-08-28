# RSS Manager Add-on Repository

Este repositório contém o add-on `RSS Manager` para Home Assistant, que permite ler e guardar feeds RSS (como ShowRSS ou Jackett) para exibição em Lovelace e integração com qBittorrent.

📘 Documentação de desenvolvimento de add-ons:
<https://developers.home-assistant.io/docs/add-ons>

[![Adicionar este repositório no Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Flasttry%2Fhassio-rss-manager)

---

## 📦 Add-ons

### [RSS Manager](./addons/rss_manager)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

Este add-on faz o scraping de feeds RSS e expõe uma API para integração com a interface Lovelace e serviços como qBittorrent. Os itens são persistidos localmente para estado (`new`, `sent`, etc.).

---

## 🚀 Como usar

1. Abre o menu **Add-on Store** no Home Assistant.
2. Clica nos 3 pontos no canto superior direito > **Repositories**.
3. Adiciona este repositório: https://github.com/lasttry/hassio-rss-manager
4. Depois de aparecer o add-on, instala e inicia.
5. Configura os feeds via ficheiro ou interface (em desenvolvimento).

---

## 🧠 Notas para desenvolvimento

- O add-on usa `startup: application` e expõe a porta 8080.
- Os feeds são definidos dentro do código Python (`main.py`) e processados com `feedparser`.
- O projeto pode ser evoluído para integrar WebSockets, eventos para automações ou autenticação via token.
- O backend guarda o estado dos itens num ficheiro JSON local.

---

### ⚙️ Arquiteturas suportadas

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg
