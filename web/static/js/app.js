/**
 * Frontend Application Controller for Nebula Supermarket Ops & AI Copilot
 * Features:
 * - Real-time WebSocket event ingestion & automatic dashboard re-renders
 * - ReAct AI Copilot interactive chat interface with chips & artifact previews
 * - POS draft bill manipulation & atomic checkouts with PDF invoices
 * - Stocks & SKU inventory management
 * - Khata Ledger credit management & settlements
 * - Slide presentation (PPTX) & invoice downloads
 */

// State
const state = {
  activeView: 'dashboard',
  draftBill: null,
  socket: null,
  isChatOpen: true
};

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
  initIcons();
  initNavigation();
  initWebSocket();
  initChat();
  initModals();
  initBillingHandlers();
  initActionButtons();

  // Load Initial Data
  loadDashboardData();
  loadInventory();
  loadDraftBill();
  loadAllBills();
  loadKhata();
  loadArtifacts();
  loadPreferences();
});

function initIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

// Navigation View Switcher
function initNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const view = item.getAttribute('data-view');
      switchView(view);
    });
  });
}

function switchView(viewName) {
  state.activeView = viewName;
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.getAttribute('data-view') === viewName);
  });
  document.querySelectorAll('.view-section').forEach(el => {
    el.classList.toggle('active', el.id === `view-${viewName}`);
  });

  // Update Header title
  const titles = {
    dashboard: { title: "Live Operations Dashboard", sub: "Real-time inventory updates, live sales telemetry, and automated billing" },
    inventory: { title: "Product Inventory & Stock Catalog", sub: "Inspect SKU levels, receive inward stock shipments, and configure GST slabs" },
    billing: { title: "Billing & Point-of-Sale (POS)", sub: "Multi-turn draft cart, atomic checkout with oversell protection, and GST invoices" },
    khata: { title: "Customer Credit Ledger", sub: "Track outstanding customer balances, transaction logs, and secure payment settlements" },
    artifacts: { title: "Business Invoices & Decks", sub: "Download generated GST Tax Invoices (PDF) and Operations Strategy Decks (PPTX)" },
    preferences: { title: "Store Configuration & Memory", sub: "Preferences stored outside model context window that persist across sessions and restarts" }
  };

  const curr = titles[viewName] || titles.dashboard;
  document.getElementById('view-title').textContent = curr.title;
  document.getElementById('view-subtitle').textContent = curr.sub;

  initIcons();

  // Refresh view data
  if (viewName === 'dashboard') loadDashboardData();
  if (viewName === 'inventory') loadInventory();
  if (viewName === 'billing') { loadDraftBill(); loadAllBills(); }
  if (viewName === 'khata') loadKhata();
  if (viewName === 'artifacts') loadArtifacts();
  if (viewName === 'preferences') loadPreferences();
}

// WebSocket Setup
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;
  
  try {
    state.socket = new WebSocket(wsUrl);

    state.socket.onopen = () => {
      document.getElementById('connection-status').textContent = 'Live Telemetry Active';
      document.getElementById('connection-status').style.color = 'var(--emerald)';
      addActivityFeedItem('⚡ Connected to Real-Time Telemetry Stream', 'system');
    };

    state.socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleServerBroadcast(msg);
      } catch (e) {
        // Ping response or plain text
      }
    };

    state.socket.onclose = () => {
      document.getElementById('connection-status').textContent = 'WebSocket: Reconnecting...';
      document.getElementById('connection-status').style.color = 'var(--amber)';
      setTimeout(initWebSocket, 3000);
    };

    state.socket.onerror = () => {
      document.getElementById('connection-status').textContent = 'WebSocket: Offline';
      document.getElementById('connection-status').style.color = 'var(--rose)';
    };
  } catch (err) {
    console.warn('WebSocket init error:', err);
  }
}

// React to Real-Time Server Broadcasts
function handleServerBroadcast(event) {
  // Whenever any conversation or POS action occurs, reload active widgets
  if (event.type === 'conversation_event') {
    addActivityFeedItem(`🗣️ Chat: "${event.user_message}"`, 'chat');
    if (event.artifacts && event.artifacts.length > 0) {
      event.artifacts.forEach(art => {
        addActivityFeedItem(`📄 Generated ${art.type.toUpperCase()}: ${art.filename}`, 'artifact');
      });
      loadArtifacts();
    }
    // Refresh all data
    loadDashboardData();
    loadInventory();
    loadDraftBill();
    loadAllBills();
    loadKhata();
  } else if (event.type === 'stock_updated') {
    addActivityFeedItem(`📦 Stock inward: ${event.item} (+${event.quantity_added}) -> Now: ${event.new_stock}`, 'stock');
    showToast(`Stock updated for ${event.item}`, 'success');
    loadInventory();
    loadDashboardData();
  } else if (event.type === 'product_added') {
    addActivityFeedItem(`✨ New SKU registered: ${event.product.name}`, 'stock');
    showToast(`New SKU registered: ${event.product.name}`, 'success');
    loadInventory();
    loadDashboardData();
  } else if (event.type === 'draft_updated') {
    loadDraftBill();
  } else if (event.type === 'bill_finalized') {
    addActivityFeedItem(`🧾 Bill finalized: ${event.bill.bill_number} (₹${event.bill.rounded_total})`, 'bill');
    showToast(`Bill ${event.bill.bill_number} finalized!`, 'success');
    loadDashboardData();
    loadAllBills();
    loadDraftBill();
    loadInventory();
    loadArtifacts();
  } else if (event.type === 'khata_updated') {
    const actionLabel = event.action === 'credit' ? 'Credit added' : 'Payment received';
    addActivityFeedItem(`💳 Credit ledger updated: ${event.customer} (${actionLabel}) -> Balance: ₹${event.new_balance}`, 'khata');
    showToast(`Credit ledger updated for ${event.customer}`, 'success');
    loadKhata();
    loadDashboardData();
  } else if (event.type === 'store_reset') {
    showToast('Store database reset to seed state!', 'warning');
    addActivityFeedItem('🔄 Store DB & catalog restored to pristine state', 'system');
    loadDashboardData();
    loadInventory();
    loadDraftBill();
    loadAllBills();
    loadKhata();
  } else if (event.type === 'artifact_created') {
    showToast(`Generated ${event.artifact_type.toUpperCase()}: ${event.filename}`, 'success');
    loadArtifacts();
  }
}

function addActivityFeedItem(text, kind = 'info') {
  const feed = document.getElementById('live-activity-feed');
  if (!feed) return;

  const item = document.createElement('div');
  item.className = 'activity-item';
  const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  
  let icon = '⚡';
  let bg = 'rgba(99,102,241,0.2)';
  if (kind === 'chat') { icon = '💬'; bg = 'rgba(6,182,212,0.2)'; }
  if (kind === 'stock') { icon = '📦'; bg = 'rgba(16,185,129,0.2)'; }
  if (kind === 'bill') { icon = '🧾'; bg = 'rgba(245,158,11,0.2)'; }
  if (kind === 'artifact') { icon = '📑'; bg = 'rgba(139,92,246,0.2)'; }

  item.innerHTML = `
    <div class="activity-item-icon" style="background:${bg}">${icon}</div>
    <div style="flex:1">
      <div>${text}</div>
      <div style="color:var(--text-dim);font-size:0.7rem">${now}</div>
    </div>
  `;

  feed.prepend(item);
  // Keep last 25 items
  while (feed.children.length > 25) {
    feed.removeChild(feed.lastChild);
  }
}

// ----------------- DATA LOADERS -----------------

// 1. Dashboard Stats
async function loadDashboardData() {
  try {
    const res = await fetch('/api/dashboard/stats');
    const data = await res.json();

    document.getElementById('stat-today-sales').textContent = `₹${(data.today_stats.gross_sales || 0).toFixed(2)}`;
    document.getElementById('stat-today-bills').textContent = `${data.today_stats.bill_count || 0} bills generated today`;
    document.getElementById('stat-total-products').textContent = data.total_products || 0;
    document.getElementById('stat-all-time-sales').textContent = `All-time: ₹${(data.all_time_sales || 0).toFixed(2)} (${data.all_time_bills || 0} bills)`;
    document.getElementById('stat-low-stock').textContent = data.low_stock_count || 0;
    document.getElementById('stat-out-of-stock').textContent = `${data.out_of_stock_count || 0} zero stock items`;
    document.getElementById('stat-khata-owed').textContent = `₹${(data.total_khata_owed || 0).toFixed(2)}`;

    // Populate Recent Transactions Table
    const tbody = document.getElementById('dashboard-recent-bills-tbody');
    if (tbody) {
      if (!data.recent_bills || data.recent_bills.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text-dim)">No bills finalized yet</td></tr>`;
      } else {
        tbody.innerHTML = data.recent_bills.map(b => `
          <tr>
            <td><strong>${b.bill_number}</strong></td>
            <td>${b.customer_name || 'Walk-in'}</td>
            <td><span class="badge badge-draft">${(b.payment_mode || 'cash').toUpperCase()}</span></td>
            <td>₹${b.subtotal.toFixed(2)}</td>
            <td>₹${b.total_tax.toFixed(2)}</td>
            <td><strong style="color:#34d399">₹${b.rounded_total.toFixed(2)}</strong></td>
            <td>
              <a href="/api/artifacts/download?filename=${b.bill_number}.pdf&type=pdf" target="_blank" class="btn btn-outline" style="padding:2px 8px;font-size:0.7rem">
                PDF
              </a>
            </td>
          </tr>
        `).join('');
      }
    }

    // Populate Top Items Today Table
    const topTbody = document.getElementById('dashboard-top-items-tbody');
    if (topTbody) {
      if (!data.top_items_today || data.top_items_today.length === 0) {
        topTbody.innerHTML = `<tr><td colspan="3" style="text-align:center;color:var(--text-dim)">No items sold today yet</td></tr>`;
      } else {
        topTbody.innerHTML = data.top_items_today.map(item => `
          <tr>
            <td><strong>${item.product_name}</strong></td>
            <td>${item.total_qty} ${item.unit}</td>
            <td><strong>₹${item.total_revenue.toFixed(2)}</strong></td>
          </tr>
        `).join('');
      }
    }

    // Populate Low Stock list
    loadLowStockList();
  } catch (err) {
    console.error('Error loading dashboard stats:', err);
  }
}

async function loadLowStockList() {
  try {
    const res = await fetch('/api/products/low-stock');
    const data = await res.json();
    const container = document.getElementById('low-stock-list');
    if (!container) return;

    if (!data.low_stock_items || data.low_stock_items.length === 0) {
      container.innerHTML = `<div style="font-size:0.8rem;color:#34d399">✓ All catalog items have healthy stock levels.</div>`;
      return;
    }

    container.innerHTML = data.low_stock_items.slice(0, 5).map(item => `
      <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 10px;background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.2);border-radius:8px">
        <div>
          <div style="font-weight:600;font-size:0.82rem">${item.name}</div>
          <div style="font-size:0.7rem;color:var(--text-dim)">Reorder Threshold: ${item.reorder_level} ${item.unit}</div>
        </div>
        <div style="text-align:right">
          <span class="badge ${item.stock_qty === 0 ? 'badge-out-of-stock' : 'badge-low-stock'}">
            ${item.stock_qty} ${item.unit} left
          </span>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Error loading low stock list:', err);
  }
}

// 2. Inventory & Stock Catalog
async function loadInventory() {
  try {
    const query = document.getElementById('inventory-search') ? document.getElementById('inventory-search').value : '';
    const res = await fetch(`/api/products?query=${encodeURIComponent(query)}`);
    const data = await res.json();
    const tbody = document.getElementById('inventory-table-tbody');
    if (!tbody) return;

    if (!data.products || data.products.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;color:var(--text-dim)">No products match your search.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.products.map(p => {
      let statusBadge = '<span class="badge badge-in-stock">In Stock</span>';
      if (p.stock_qty === 0) statusBadge = '<span class="badge badge-out-of-stock">Out of Stock</span>';
      else if (p.stock_qty <= p.reorder_level) statusBadge = '<span class="badge badge-low-stock">Low Stock</span>';

      return `
        <tr>
          <td><code style="font-size:0.75rem">${p.sku_id}</code></td>
          <td><strong>${p.name}</strong> ${p.brand ? `<small style="color:var(--text-dim)">(${p.brand})</small>` : ''}</td>
          <td>${p.category || 'General'}</td>
          <td><strong>${p.stock_qty}</strong> ${p.unit}</td>
          <td>${p.reorder_level} ${p.unit}</td>
          <td>₹${p.cost_price.toFixed(2)}</td>
          <td>₹${p.sell_price.toFixed(2)}</td>
          <td>${(p.gst_rate * 100).toFixed(0)}%</td>
          <td>${statusBadge}</td>
          <td>
            <button class="btn btn-outline" style="padding:3px 8px;font-size:0.72rem" onclick="openInwardForProduct('${p.name}')">
              + Inward
            </button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading inventory:', err);
  }
}

function openInwardForProduct(prodName) {
  document.getElementById('inward-product-name').value = prodName;
  document.getElementById('modal-inward').classList.add('active');
}

// 3. Billing & Draft POS
async function loadDraftBill() {
  try {
    const res = await fetch('/api/draft-bill');
    const bill = await res.json();
    state.draftBill = bill;

    document.getElementById('draft-bill-number').textContent = bill.bill_number;
    document.getElementById('draft-taxable').textContent = `₹${(bill.subtotal || 0).toFixed(2)}`;
    document.getElementById('draft-gst').textContent = `₹${(bill.total_tax || 0).toFixed(2)}`;
    document.getElementById('draft-grand-total').textContent = `₹${(bill.rounded_total || 0).toFixed(2)}`;

    const tbody = document.getElementById('draft-items-tbody');
    if (!tbody) return;

    if (!bill.items || bill.items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;color:var(--text-dim);padding:24px">No items on draft bill yet. You can speak to Copilot or use Quick Add!</td></tr>`;
      return;
    }

    tbody.innerHTML = bill.items.map((it, idx) => `
      <tr>
        <td>${idx + 1}</td>
        <td><strong>${it.product_name}</strong></td>
        <td>${it.hsn_code}</td>
        <td>${it.quantity} ${it.unit}</td>
        <td>₹${it.unit_price.toFixed(2)}</td>
        <td>₹${it.taxable_value.toFixed(2)}</td>
        <td>₹${it.cgst.toFixed(2)}</td>
        <td>₹${it.sgst.toFixed(2)}</td>
        <td><strong>₹${it.total_price.toFixed(2)}</strong></td>
        <td>
          <button class="btn btn-danger" style="padding:2px 8px;font-size:0.72rem" onclick="removeDraftItem('${it.product_name}')">
            Remove
          </button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Error loading draft bill:', err);
  }
}

async function removeDraftItem(itemName) {
  try {
    const res = await fetch(`/api/draft-bill/items/${encodeURIComponent(itemName)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    loadDraftBill();
  } catch (err) {
    showToast(`Failed to remove item: ${err.message}`, 'error');
  }
}

async function loadAllBills() {
  try {
    const res = await fetch('/api/bills');
    const data = await res.json();
    const tbody = document.getElementById('all-bills-tbody');
    if (!tbody) return;

    if (!data.bills || data.bills.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;color:var(--text-dim)">No bills registered</td></tr>`;
      return;
    }

    tbody.innerHTML = data.bills.map(b => `
      <tr>
        <td><strong>${b.bill_number}</strong></td>
        <td>${b.created_at}</td>
        <td>${b.customer_name || 'Walk-in'}</td>
        <td><span class="badge badge-draft">${(b.payment_mode || 'cash').toUpperCase()}</span></td>
        <td>₹${b.subtotal.toFixed(2)}</td>
        <td>₹${b.total_tax.toFixed(2)}</td>
        <td><strong>₹${b.rounded_total.toFixed(2)}</strong></td>
        <td>
          <span class="badge ${b.status === 'finalized' ? 'badge-finalized' : 'badge-draft'}">
            ${b.status}
          </span>
        </td>
        <td>
          <a href="/api/artifacts/download?filename=${b.bill_number}.pdf&type=pdf" target="_blank" class="btn btn-outline" style="padding:2px 8px;font-size:0.72rem">
            Download PDF
          </a>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Error loading all bills:', err);
  }
}

// 4. Khata Ledger
async function loadKhata() {
  try {
    const res = await fetch('/api/khata');
    const data = await res.json();

    const custCount = (data.customers || []).length;
    const totalOut = (data.customers || []).reduce((acc, c) => acc + (c.balance || 0), 0);
    document.getElementById('khata-customer-count').textContent = custCount;
    document.getElementById('khata-total-outstanding').textContent = `₹${totalOut.toFixed(2)}`;

    // Customers Table
    const tbody = document.getElementById('khata-customers-tbody');
    if (tbody) {
      if (!data.customers || data.customers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-dim)">No customers registered in Khata</td></tr>`;
      } else {
        tbody.innerHTML = data.customers.map(c => `
          <tr>
            <td><strong>${c.name}</strong></td>
            <td>${c.phone || '---'}</td>
            <td><strong style="color:${c.balance > 0 ? '#fbbf24' : '#34d399'}">₹${c.balance.toFixed(2)}</strong></td>
            <td>${c.updated_at || c.created_at}</td>
            <td>
              <button class="btn btn-outline" style="padding:2px 8px;font-size:0.72rem" onclick="openKhataModal('credit', '${c.name}')">+ Credit</button>
              <button class="btn btn-success" style="padding:2px 8px;font-size:0.72rem" onclick="openKhataModal('settlement', '${c.name}', ${c.balance})">Settle</button>
            </td>
          </tr>
        `).join('');
      }
    }

    // Transactions Table
    const txTbody = document.getElementById('khata-transactions-tbody');
    if (txTbody) {
      if (!data.transactions || data.transactions.length === 0) {
        txTbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-dim)">No transactions logged</td></tr>`;
      } else {
        txTbody.innerHTML = data.transactions.map(t => `
          <tr>
            <td>${t.timestamp}</td>
            <td><strong>${t.customer_name}</strong></td>
            <td>
              <span class="badge ${t.entry_type === 'debit' ? 'badge-low-stock' : 'badge-in-stock'}">
                ${t.entry_type === 'debit' ? 'CREDIT BORROWED' : 'PAYMENT SETTLED'}
              </span>
            </td>
            <td>₹${t.amount.toFixed(2)}</td>
            <td>₹${t.balance_after.toFixed(2)}</td>
          </tr>
        `).join('');
      }
    }
  } catch (err) {
    console.error('Error loading khata:', err);
  }
}

function openKhataModal(type, customerName = '', amount = 100) {
  document.getElementById('khata-action-type').value = type;
  document.getElementById('khata-customer-name').value = customerName;
  document.getElementById('khata-amount').value = amount || 100;
  
  if (type === 'settlement') {
    document.getElementById('khata-modal-title').textContent = 'Record Customer Credit Payment';
    document.getElementById('khata-payment-mode-group').style.display = 'block';
    document.getElementById('khata-submit-btn').textContent = 'Record Payment';
    document.getElementById('khata-submit-btn').className = 'btn btn-success';
  } else {
    document.getElementById('khata-modal-title').textContent = 'Add Credit to Customer Account';
    document.getElementById('khata-payment-mode-group').style.display = 'none';
    document.getElementById('khata-submit-btn').textContent = 'Add Credit';
    document.getElementById('khata-submit-btn').className = 'btn btn-primary';
  }

  document.getElementById('modal-khata-action').classList.add('active');
}

// 5. Artifacts
async function loadArtifacts() {
  try {
    const res = await fetch('/api/artifacts');
    const data = await res.json();

    // Decks
    const decksGrid = document.getElementById('artifacts-decks-grid');
    if (decksGrid) {
      if (!data.decks || data.decks.length === 0) {
        decksGrid.innerHTML = `<div style="color:var(--text-dim);font-size:0.85rem">No PowerPoint decks generated yet. Click 'Generate Fresh PPTX Deck' above!</div>`;
      } else {
        decksGrid.innerHTML = data.decks.map(d => `
          <div class="artifact-card">
            <div>
              <div style="font-size:1.8rem;margin-bottom:8px">📊</div>
              <strong style="font-size:0.95rem;word-break:break-all">${d.filename}</strong>
              <div style="color:var(--text-muted);font-size:0.75rem;margin-top:4px">
                Size: ${d.size_kb} KB • Generated: ${d.modified}
              </div>
            </div>
            <div style="margin-top:14px">
              <a href="${d.url}" class="btn btn-primary" style="width:100%;justify-content:center" download>
                Download PPTX
              </a>
            </div>
          </div>
        `).join('');
      }
    }

    // Invoices
    const invoicesGrid = document.getElementById('artifacts-invoices-grid');
    if (invoicesGrid) {
      if (!data.invoices || data.invoices.length === 0) {
        invoicesGrid.innerHTML = `<div style="color:var(--text-dim);font-size:0.85rem">No PDF invoices generated yet.</div>`;
      } else {
        invoicesGrid.innerHTML = data.invoices.map(inv => `
          <div class="artifact-card">
            <div>
              <div style="font-size:1.8rem;margin-bottom:8px">🧾</div>
              <strong style="font-size:0.95rem;word-break:break-all">${inv.filename}</strong>
              <div style="color:var(--text-muted);font-size:0.75rem;margin-top:4px">
                Size: ${inv.size_kb} KB • Date: ${inv.modified}
              </div>
            </div>
            <div style="margin-top:14px">
              <a href="${inv.url}" target="_blank" class="btn btn-outline" style="width:100%;justify-content:center">
                View / Download PDF
              </a>
            </div>
          </div>
        `).join('');
      }
    }
  } catch (err) {
    console.error('Error loading artifacts:', err);
  }
}

// 6. Preferences
async function loadPreferences() {
  try {
    const res = await fetch('/api/preferences');
    const prefs = await res.json();
    const tbody = document.getElementById('preferences-tbody');
    if (!tbody) return;

    const entries = Object.entries(prefs);
    if (entries.length === 0) {
      tbody.innerHTML = `<tr><td colspan="2" style="text-align:center;color:var(--text-dim)">No preferences configured</td></tr>`;
      return;
    }

    tbody.innerHTML = entries.map(([k, v]) => `
      <tr>
        <td><code>${k}</code></td>
        <td><strong>${v}</strong></td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Error loading preferences:', err);
  }
}

// ----------------- CHATBOT COPILOT -----------------

function initChat() {
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const drawer = document.getElementById('chat-drawer');
  const toggleBtn = document.getElementById('toggle-chat-btn');
  const closeBtn = document.getElementById('btn-close-chat');
  const resetBtn = document.getElementById('btn-reset-chat');

  toggleBtn.addEventListener('click', () => {
    state.isChatOpen = !state.isChatOpen;
    drawer.classList.toggle('collapsed', !state.isChatOpen);
    if (state.isChatOpen) input.focus();
  });

  closeBtn.addEventListener('click', () => {
    state.isChatOpen = false;
    drawer.classList.add('collapsed');
  });

  resetBtn.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/chat/reset', { method: 'POST' });
      const data = await res.json();
      appendChatMessage('agent', `🔄 ${data.message}`);
      loadDraftBill();
    } catch (err) {
      showToast('Error resetting chat', 'error');
    }
  });

  // Prompt chips
  document.querySelectorAll('.prompt-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      input.value = chip.getAttribute('data-prompt');
      form.dispatchEvent(new Event('submit'));
    });
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    appendChatMessage('user', text);
    input.value = '';

    // Show animated typing state with isHtml=true
    const typingIndicatorHtml = `
      <div class="typing-indicator">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-label">Thinking...</span>
      </div>
    `;
    const typingId = appendChatMessage('agent', typingIndicatorHtml, true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: 'web_shopkeeper_session' })
      });

      const data = await res.json();
      removeChatMessage(typingId);

      // Format agent response using markdown parser
      let replyHtml = formatMarkdown(data.reply);

      // Tools pill
      if (data.tools_executed && data.tools_executed.length > 0) {
        replyHtml += `<div style="margin-top:8px">` + 
          data.tools_executed.map(t => `<span class="tool-badge-pill">⚙️ ${t}</span>`).join(' ') +
          `</div>`;
      }

      // Generated artifacts embed
      if (data.artifacts && data.artifacts.length > 0) {
        replyHtml += `<div style="margin-top:8px">`;
        data.artifacts.forEach(art => {
          replyHtml += `
            <div class="artifact-card-embed">
              <div class="artifact-info">
                <span>${art.type === 'pdf' ? '🧾' : '📊'}</span>
                <strong>${art.filename}</strong>
              </div>
              <a href="${art.url}" target="_blank" class="btn btn-primary" style="padding:4px 10px;font-size:0.75rem">
                Open
              </a>
            </div>
          `;
        });
        replyHtml += `</div>`;
      }

      appendChatMessage('agent', replyHtml, true);
    } catch (err) {
      removeChatMessage(typingId);
      appendChatMessage('agent', `⚠️ Failed to reach assistant: ${err.message}`, true);
    }
  });
}

function formatMarkdown(text) {
  if (!text) return "";
  let s = text;

  // Escape basic HTML tags to prevent injection while keeping formatting clean
  s = s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // Bold: **text** or __text__ -> <strong>text</strong>
  s = s.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/__(.*?)__/g, "<strong>$1</strong>");

  // Italic: *text* or _text_ -> <em>$1</em> (avoid matching lone asterisks)
  s = s.replace(/(^|[^*])\*([^*]+)\*([^*]|$)/g, "$1<em>$2</em>$3");
  s = s.replace(/(^|[^_])_([^_]+)_([^_]|$)/g, "$1<em>$2</em>$3");

  // Clean up any remaining stray asterisks
  s = s.replace(/\*/g, "");

  // Bullet points: lines starting with "- " or "• "
  const lines = s.split("\n");
  const formattedLines = [];
  for (let line of lines) {
    let trimmed = line.trim();
    if (trimmed.startsWith("- ") || trimmed.startsWith("• ")) {
      formattedLines.push(`<div style="display:flex;gap:6px;margin:2px 0"><span style="color:var(--primary);font-weight:bold">•</span><span>${trimmed.substring(2)}</span></div>`);
    } else if (trimmed) {
      formattedLines.push(`<div>${trimmed}</div>`);
    } else {
      formattedLines.push(`<div style="height:6px"></div>`);
    }
  }

  return formattedLines.join("");
}

function appendChatMessage(sender, rawContent, isHtml = false) {
  const container = document.getElementById('chat-messages');
  const msgEl = document.createElement('div');
  const msgId = 'msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 4);
  msgEl.id = msgId;
  msgEl.className = `chat-msg ${sender}`;
  
  const contentHtml = isHtml ? rawContent : (sender === 'agent' ? formatMarkdown(rawContent) : rawContent.replace(/\n/g, '<br>'));
  msgEl.innerHTML = `<div class="chat-bubble">${contentHtml}</div>`;
  container.appendChild(msgEl);
  container.scrollTop = container.scrollHeight;
  return msgId;
}

function removeChatMessage(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ----------------- MODALS & FORMS -----------------

function initModals() {
  document.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('active'));
    });
  });

  // Modal triggers
  const btnInward = document.getElementById('btn-open-inward-modal');
  if (btnInward) btnInward.addEventListener('click', () => document.getElementById('modal-inward').classList.add('active'));

  const btnSku = document.getElementById('btn-open-new-sku-modal');
  if (btnSku) btnSku.addEventListener('click', () => document.getElementById('modal-new-sku').classList.add('active'));

  const btnFinalize = document.getElementById('btn-open-finalize-modal');
  if (btnFinalize) btnFinalize.addEventListener('click', () => document.getElementById('modal-finalize-bill').classList.add('active'));

  const btnKhataCredit = document.getElementById('btn-open-khata-credit-modal');
  if (btnKhataCredit) btnKhataCredit.addEventListener('click', () => openKhataModal('credit'));

  const btnKhataSettle = document.getElementById('btn-open-khata-settle-modal');
  if (btnKhataSettle) btnKhataSettle.addEventListener('click', () => openKhataModal('settlement'));

  // Inward Form
  const formInward = document.getElementById('form-inward');
  if (formInward) {
    formInward.addEventListener('submit', async (e) => {
      e.preventDefault();
      const body = {
        sku_or_name: document.getElementById('inward-product-name').value,
        quantity: parseFloat(document.getElementById('inward-quantity').value),
        cost_price: document.getElementById('inward-cost').value ? parseFloat(document.getElementById('inward-cost').value) : null,
        mrp: document.getElementById('inward-mrp').value ? parseFloat(document.getElementById('inward-mrp').value) : null
      };
      try {
        const res = await fetch('/api/products/receive-stock', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        if (!res.ok) throw new Error(await res.text());
        document.getElementById('modal-inward').classList.remove('active');
        formInward.reset();
        showToast('Stock received successfully!', 'success');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  // New SKU Form
  const formSku = document.getElementById('form-new-sku');
  if (formSku) {
    formSku.addEventListener('submit', async (e) => {
      e.preventDefault();
      const body = {
        name: document.getElementById('sku-name').value,
        category: document.getElementById('sku-category').value,
        unit: document.getElementById('sku-unit').value,
        cost_price: parseFloat(document.getElementById('sku-cost').value),
        mrp: parseFloat(document.getElementById('sku-mrp').value),
        gst_rate: parseFloat(document.getElementById('sku-gst').value),
        initial_stock: parseFloat(document.getElementById('sku-stock').value)
      };
      try {
        const res = await fetch('/api/products', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        if (!res.ok) throw new Error(await res.text());
        document.getElementById('modal-new-sku').classList.remove('active');
        formSku.reset();
        showToast('New SKU registered!', 'success');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  // Finalize Form
  const formFinalize = document.getElementById('form-finalize-bill');
  if (formFinalize) {
    formFinalize.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!state.draftBill || !state.draftBill.bill_id) {
        showToast('No active draft bill to finalize', 'error');
        return;
      }
      const body = {
        bill_id: state.draftBill.bill_id,
        payment_mode: document.getElementById('finalize-payment-mode').value,
        customer_name: document.getElementById('finalize-customer-name').value || 'Walk-in Customer',
        payment_ref: document.getElementById('finalize-payment-ref').value || null
      };
      try {
        const res = await fetch('/api/bills/finalize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        document.getElementById('modal-finalize-bill').classList.remove('active');
        formFinalize.reset();
        showToast(`Bill finalized! Grand total: ₹${data.bill.rounded_total}`, 'success');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  // Khata Action Form
  const formKhata = document.getElementById('form-khata-action');
  if (formKhata) {
    formKhata.addEventListener('submit', async (e) => {
      e.preventDefault();
      const type = document.getElementById('khata-action-type').value;
      const endpoint = type === 'settlement' ? '/api/khata/settlement' : '/api/khata/credit';
      const body = {
        customer_name: document.getElementById('khata-customer-name').value,
        amount: parseFloat(document.getElementById('khata-amount').value),
        payment_mode: document.getElementById('khata-payment-mode').value,
        notes: document.getElementById('khata-notes').value || null
      };
      try {
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        if (!res.ok) throw new Error(await res.text());
        document.getElementById('modal-khata-action').classList.remove('active');
        formKhata.reset();
        showToast(`Khata ${type} successful!`, 'success');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }
}

// POS Handlers
function initBillingHandlers() {
  const btnQuickAdd = document.getElementById('btn-quick-add-item');
  if (btnQuickAdd) {
    btnQuickAdd.addEventListener('click', async () => {
      const name = document.getElementById('quick-add-item-name').value.trim();
      const qty = parseFloat(document.getElementById('quick-add-item-qty').value) || 1.0;
      if (!name) return;

      try {
        const res = await fetch('/api/draft-bill/items', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ item_name: name, quantity: qty })
        });
        if (!res.ok) throw new Error(await res.text());
        document.getElementById('quick-add-item-name').value = '';
        loadDraftBill();
        showToast(`Added ${qty} ${name} to bill`, 'success');
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  const btnClearDraft = document.getElementById('btn-clear-draft');
  if (btnClearDraft) {
    btnClearDraft.addEventListener('click', async () => {
      await fetch('/api/chat/reset', { method: 'POST' });
      loadDraftBill();
      showToast('Draft bill cleared', 'warning');
    });
  }

  const searchInput = document.getElementById('inventory-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      loadInventory();
    });
  }
}

function initActionButtons() {
  const btnResetDb = document.getElementById('btn-reset-db');
  if (btnResetDb) {
    btnResetDb.addEventListener('click', async () => {
      if (confirm('Are you sure you want to restore the store database to its initial seed state? This wipes test transactions.')) {
        try {
          const res = await fetch('/api/system/reset-db', { method: 'POST' });
          if (!res.ok) throw new Error(await res.text());
        } catch (err) {
          showToast(err.message, 'error');
        }
      }
    });
  }

  const btnGenPptx = document.getElementById('btn-gen-pptx');
  if (btnGenPptx) {
    btnGenPptx.addEventListener('click', async () => {
      showToast('Generating PowerPoint deck... ⏳', 'warning');
      try {
        const res = await fetch('/api/artifacts/generate-pptx?days=7', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
          showToast('PowerPoint deck generated successfully!', 'success');
          loadArtifacts();
        } else {
          showToast(data.message, 'error');
        }
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }

  const btnGenPptxView = document.getElementById('btn-generate-deck-now');
  if (btnGenPptxView) {
    btnGenPptxView.addEventListener('click', () => {
      if (btnGenPptx) btnGenPptx.click();
    });
  }

  const btnNewBill = document.getElementById('btn-quick-new-bill');
  if (btnNewBill) {
    btnNewBill.addEventListener('click', () => {
      switchView('billing');
    });
  }

  const btnSavePref = document.getElementById('btn-save-preference');
  if (btnSavePref) {
    btnSavePref.addEventListener('click', async () => {
      const key = document.getElementById('pref-key-input').value.trim();
      const val = document.getElementById('pref-val-input').value.trim();
      if (!key || !val) {
        showToast('Please provide both key and value', 'warning');
        return;
      }
      try {
        const res = await fetch('/api/preferences', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key, value: val })
        });
        if (!res.ok) throw new Error(await res.text());
        document.getElementById('pref-key-input').value = '';
        document.getElementById('pref-val-input').value = '';
        showToast(`Saved preference: ${key} = ${val}`, 'success');
        loadPreferences();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  }
}

// Toast Notifications
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
