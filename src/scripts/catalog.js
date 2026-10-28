(function (global) {
  'use strict';

  var CATEGORIES = Object.freeze(['Cabello', 'Rostro', 'Uñas', 'Piel']);
  var CATEGORY_COUNTS = Object.freeze({ Cabello: 8, Rostro: 7, Uñas: 6, Piel: 3 });
  var DETAIL_IDS = Object.freeze(['corte-de-cabello', 'coloracion-con-tinte', 'henna-capilar']);

  function normalize(value) {
    return String(value == null ? '' : value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es').trim();
  }

  function sortRecords(records, order) {
    var direction = order === 'title-desc' ? -1 : 1;
    return records.slice().sort(function (left, right) {
      return direction * normalize(left.name).localeCompare(normalize(right.name), 'es');
    });
  }

  function isSafeAsset(path) {
    return typeof path === 'string' && /^assets\/services\/[a-z0-9-]+\/[a-z0-9_-]+\.png$/.test(path) && !path.includes('..');
  }

  function validServices(records) {
    if (!Array.isArray(records) || records.length !== 24) return false;
    var ids = new Set();
    var counts = { Cabello: 0, Rostro: 0, Uñas: 0, Piel: 0 };
    var ready = [];
    var valid = records.every(function (record) {
      if (!record || typeof record !== 'object' || !/^[a-z0-9-]+$/.test(record.id || '') || ids.has(record.id) ||
          typeof record.name !== 'string' || !record.name.trim() || !Object.prototype.hasOwnProperty.call(counts, record.category) ||
          record.listed !== true || !Array.isArray(record.variants) || !record.variants.every(function (value) { return typeof value === 'string'; }) ||
          !['ready', 'pending'].includes(record.detailStatus) || !Array.isArray(record.description) ||
          !record.description.every(function (value) { return typeof value === 'string'; }) || !Array.isArray(record.gallery)) return false;
      ids.add(record.id);
      counts[record.category] += 1;
      if (record.detailStatus === 'ready') {
        ready.push(record.id);
        if (record.detailPath !== 'servicios/' + record.id + '/' || !record.description.length || !isSafeAsset(record.cover) ||
            !record.gallery.length || !record.gallery.every(isSafeAsset) || typeof record.imageAlt !== 'string' || !record.imageAlt.trim() ||
            typeof record.whatsappMessage !== 'string' || !record.whatsappMessage.trim()) return false;
      } else if (record.detailPath !== null || (record.cover !== null && !isSafeAsset(record.cover)) || !record.gallery.every(isSafeAsset)) return false;
      return true;
    });
    return valid && CATEGORIES.every(function (name) { return counts[name] === CATEGORY_COUNTS[name]; }) &&
      DETAIL_IDS.every(function (id) { return ready.includes(id); }) && ready.length === DETAIL_IDS.length;
  }

  function matches(record, query, category) {
    var haystack = normalize([record.name].concat(record.variants || []).join(' '));
    return (!query || haystack.includes(normalize(query))) && (!category || record.category === category);
  }

  function validProducts(records) {
    if (!Array.isArray(records)) return false;
    var ids = new Set();
    return records.every(function (record) {
      if (!record || typeof record !== 'object' || !/^[a-z0-9-]+$/.test(record.id || '') || ids.has(record.id) ||
          typeof record.name !== 'string' || !record.name.trim() || typeof record.group !== 'string' || !record.group.trim() ||
          record.detailPath !== 'productos/' + record.id + '/' || !Array.isArray(record.gallery) || record.gallery.length < 2 ||
          !record.gallery.every(function (path) { return /^assets\/products\/[a-z0-9-]+\.svg$/.test(path) && !path.includes('..'); }) ||
          (record.previewLabel != null && (typeof record.previewLabel !== 'string' || record.previewLabel.length > 60))) return false;
      ids.add(record.id);
      return true;
    });
  }

  function initProductCatalog(root) {
    var status = root.querySelector('[data-catalog-status]');
    var source = root.getAttribute('data-catalog-data');
    if (!status || !source) return;
    fetch(source, { credentials: 'omit', cache: 'no-store' }).then(function (response) {
      if (!response.ok) throw new Error('No se pudo cargar el catálogo local.');
      return response.json();
    }).then(function (records) {
      if (!validProducts(records)) throw new Error('El catálogo no cumple el esquema autorizado.');
      var form = root.querySelector('[data-catalog-form]');
      var search = form.querySelector('[name="q"]');
      var sort = root.querySelector('[name="order"]');
      var reset = form.querySelector('[type="reset"]');
      var grid = root.querySelector('[data-catalog-grid]');
      var count = root.querySelector('[data-catalog-count]');
      var empty = root.querySelector('[data-catalog-empty]');
      var categories = form.querySelector('[data-product-categories]');
      var initialCategory = categories.querySelector('[name="category"]');
      var radios = [initialCategory];
      var base = root.getAttribute('data-base-path');

      Array.from(new Set(records.map(function (record) { return record.group; }))).sort(function (left, right) {
        return normalize(left).localeCompare(normalize(right), 'es');
      }).forEach(function (group) {
        var label = document.createElement('label');
        label.className = 'lc-products__filter-option';
        var input = document.createElement('input');
        input.type = 'radio';
        input.name = 'category';
        input.value = group;
        var text = document.createElement('span');
        text.textContent = group;
        var badge = document.createElement('span');
        badge.dataset.categoryCount = group;
        label.append(input, text, badge);
        categories.append(label);
        radios.push(input);
      });
      function makeCard(record) {
        var card = document.createElement('article');
        card.className = 'lc-products__card';
        var link = document.createElement('a');
        link.className = 'lc-products__card-link';
        link.href = base + record.detailPath;
        link.setAttribute('aria-label', 'Abrir ficha de demostración: ' + record.name);
        var media = document.createElement('div');
        media.className = 'lc-products__media';
        var image = document.createElement('img');
        image.src = base + record.gallery[0];
        image.alt = '';
        image.width = 800;
        image.height = 800;
        image.loading = 'lazy';
        image.decoding = 'async';
        media.append(image);
        var body = document.createElement('div');
        body.className = 'lc-catalog__card-body';
        var group = document.createElement('p');
        group.className = 'lc-products__category';
        group.textContent = record.group;
        var title = document.createElement('h2');
        title.textContent = record.name;
        var note = document.createElement('p');
        note.className = 'lc-products__card-note';
        note.textContent = 'Conocer producto';
        body.append(group, title);
        if (record.previewLabel) {
          var badge = document.createElement('span');
          badge.className = 'lc-products__demo-badge';
          badge.textContent = record.previewLabel;
          body.append(badge);
        }
        body.append(note);
        link.append(media, body);
        card.append(link);
        return card;
      }

      function render() {
        var selected = radios.find(function (radio) { return radio.checked; });
        var group = selected && selected.value !== 'all' ? selected.value : '';
        var results = sortRecords(records.filter(function (record) {
          return (!group || record.group === group) && (!search.value || normalize(record.name + ' ' + record.group).includes(normalize(search.value)));
        }), sort.value);
        grid.replaceChildren();
        results.forEach(function (record) { grid.append(makeCard(record)); });
        root.querySelectorAll('[data-category-count]').forEach(function (badge) {
          var category = badge.getAttribute('data-category-count');
          badge.textContent = String(category === 'all' ? records.length : records.filter(function (record) { return record.group === category; }).length);
        });
        count.textContent = results.length + (results.length === 1 ? ' resultado' : ' resultados');
        status.textContent = records.length ? 'Se muestran ' + results.length + ' de ' + records.length + ' productos.' : 'Aún no hay productos publicados.';
        grid.hidden = results.length === 0;
        empty.hidden = results.length > 0;
      }

      search.disabled = false;
      sort.disabled = false;
      reset.disabled = false;
      categories.disabled = false;
      categories.hidden = records.length === 0;
      search.addEventListener('input', render);
      sort.addEventListener('change', render);
      radios.forEach(function (radio) { radio.addEventListener('change', render); });
      form.addEventListener('reset', function () { sort.value = 'title-asc'; global.setTimeout(render, 0); });
      render();
    }).catch(function () {
      status.textContent = 'No fue posible cargar el registro local de productos.';
      status.setAttribute('role', 'alert');
    });
  }

  function initServiceCatalog(root) {
    var status = root.querySelector('[data-catalog-status]');
    var source = root.getAttribute('data-catalog-data');
    if (!status || !source) return;

    fetch(source, { credentials: 'omit', cache: 'no-store' }).then(function (response) {
      if (!response.ok) throw new Error('No se pudo cargar el catálogo local.');
      return response.json();
    }).then(function (records) {
      if (!validServices(records)) throw new Error('El registro local de servicios no cumple su esquema aprobado.');
      var services = records.filter(function (record) { return record.listed; });
      var form = root.querySelector('[data-catalog-form]');
      var search = form.querySelector('[name="q"]');
      var sort = root.querySelector('[name="order"]');
      var reset = form.querySelector('[type="reset"]');
      var grid = root.querySelector('[data-catalog-grid]');
      var count = root.querySelector('[data-catalog-count]');
      var empty = root.querySelector('[data-catalog-empty]');
      var radios = Array.from(form.querySelectorAll('[name="category"]'));
      var base = root.getAttribute('data-base-path');
      var categoryCounts = Object.create(null);
      services.forEach(function (record) { categoryCounts[record.category] = (categoryCounts[record.category] || 0) + 1; });
      root.querySelectorAll('[data-category-count]').forEach(function (badge) {
        var category = badge.getAttribute('data-category-count');
        badge.textContent = String(category === 'all' ? services.length : (categoryCounts[category] || 0));
      });

      function makeCard(record) {
        var card = document.createElement('article');
        card.className = 'lc-catalog__card lc-services__card';
        card.dataset.serviceId = record.id;
        card.dataset.detailStatus = record.detailStatus;
        var content = record.detailStatus === 'ready' ? document.createElement('a') : document.createElement('div');
        content.className = 'lc-services__card-content';
        if (record.detailStatus === 'ready') {
          content.href = base + record.detailPath;
          content.setAttribute('aria-label', 'Conocer el servicio: ' + record.name);
        }
        var media = document.createElement('div');
        media.className = 'lc-catalog__card-media lc-services__card-media';
        if (record.cover) {
          var image = document.createElement('img');
          image.src = base + record.cover;
          image.alt = '';
          image.width = 1254;
          image.height = 1254;
          image.loading = 'lazy';
          image.decoding = 'async';
          image.addEventListener('error', function () { media.textContent = 'Imagen no disponible'; }, { once: true });
          media.append(image);
        } else {
          var placeholder = document.createElement('span');
          placeholder.className = 'lc-services__placeholder';
          placeholder.setAttribute('aria-hidden', 'true');
          media.append(placeholder);
        }
        var body = document.createElement('div');
        body.className = 'lc-catalog__card-body';
        var label = document.createElement('p');
        label.className = 'lc-catalog__category';
        label.textContent = record.category;
        var title = document.createElement('h2');
        title.textContent = record.name;
        body.append(label, title);
        if (record.detailStatus === 'ready') {
          var cta = document.createElement('span');
          cta.className = 'lc-services__card-cta';
          cta.textContent = 'Conocer el servicio';
          body.append(cta);
        } else {
          var pending = document.createElement('p');
          pending.className = 'lc-services__pending';
          pending.textContent = 'Información en preparación';
          body.append(pending);
        }
        content.append(media, body);
        card.append(content);
        return card;
      }

      function render() {
        var selected = radios.find(function (radio) { return radio.checked; });
        var category = selected && selected.value !== 'all' ? selected.value : '';
        var results = sortRecords(services.filter(function (record) { return matches(record, search.value, category); }), sort.value);
        grid.replaceChildren();
        results.forEach(function (record) { grid.append(makeCard(record)); });
        count.textContent = results.length + (results.length === 1 ? ' resultado' : ' resultados');
        status.textContent = 'Se muestran ' + results.length + ' de ' + services.length + ' servicios listados.';
        grid.hidden = results.length === 0;
        empty.hidden = results.length > 0;
      }

      search.disabled = false;
      sort.disabled = false;
      reset.disabled = false;
      form.querySelector('.lc-services__categories').disabled = false;
      search.addEventListener('input', render);
      sort.addEventListener('change', render);
      radios.forEach(function (radio) { radio.addEventListener('change', render); });
      form.addEventListener('reset', function () {
        sort.value = 'title-asc';
        global.setTimeout(render, 0);
      });
      render();
    }).catch(function () {
      status.textContent = 'No fue posible cargar el registro local de servicios.';
      status.setAttribute('role', 'alert');
    });
  }

  function initServiceGallery(root) {
    var image = root.querySelector('[data-gallery-main]');
    var thumbs = Array.from(root.querySelectorAll('[data-gallery-thumb]'));
    if (!image || !thumbs.length) return;
    function select(button, moveFocus) {
      image.src = button.getAttribute('data-image-src');
      image.alt = button.getAttribute('data-image-alt');
      thumbs.forEach(function (thumb) {
        var active = thumb === button;
        thumb.setAttribute('aria-pressed', String(active));
        thumb.classList.toggle('is-active', active);
      });
      if (moveFocus) button.focus();
    }
    thumbs.forEach(function (button, index) {
      button.addEventListener('click', function () { select(button, false); });
      button.addEventListener('keydown', function (event) {
        var next = index;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % thumbs.length;
        else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index + thumbs.length - 1) % thumbs.length;
        else if (event.key === 'Home') next = 0;
        else if (event.key === 'End') next = thumbs.length - 1;
        else return;
        event.preventDefault();
        select(thumbs[next], true);
      });
    });
  }

  var core = Object.freeze({ normalize: normalize, sortRecords: sortRecords, matches: matches, validServices: validServices, validProducts: validProducts });
  global.LightColorCatalog = core;
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-catalog-type="services"]').forEach(initServiceCatalog);
    document.querySelectorAll('[data-catalog-type="products"]').forEach(initProductCatalog);
    document.querySelectorAll('[data-service-detail]').forEach(initServiceGallery);
    document.querySelectorAll('[data-product-detail]').forEach(initServiceGallery);
  });
}(window));
