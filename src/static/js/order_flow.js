// 発注フロー統合ページの主要機能

// ==== タブ切り替え機能 ====
document.addEventListener('DOMContentLoaded', function () {
    ensureProcessingPanelPlacement();
    initializeTabs();
    initializeImportTab();
    initializeOrdersTab();
    initializeReceivingTab();
    initializeInspectionTab();
    initializePrintTab();
    initializeProcessingTab();
});

function formatDateToJP(value) {
    if (!value) {
        return '-';
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }
    return parsed.toLocaleDateString('ja-JP');
}

function ensureProcessingPanelPlacement() {
    const container = document.getElementById('order-flow-tab-panels');
    const processingPanel = document.getElementById('panel-processing');
    if (!container || !processingPanel) {
        return;
    }
    if (!container.contains(processingPanel)) {
        container.appendChild(processingPanel);
    }
}

function initializeTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabPanels = document.querySelectorAll('.tab-panel');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetId = button.getAttribute('aria-controls');

            // すべてのタブとパネルを非アクティブ化
            tabButtons.forEach(btn => {
                btn.classList.remove('active');
                btn.setAttribute('aria-selected', 'false');
            });
            tabPanels.forEach(panel => {
                panel.classList.add('hidden');
            });

            // 選択されたタブとパネルをアクティブ化
            button.classList.add('active');
            button.setAttribute('aria-selected', 'true');
            document.getElementById(targetId).classList.remove('hidden');

            // タブ切り替え時のデータ再読込
            if (targetId === 'panel-orders') {
                loadOrders(1);
            } else if (targetId === 'panel-receiving') {
                loadReceivingItems();
            } else if (targetId === 'panel-inspection') {
                loadInspectionItemsList();
            } else if (targetId === 'panel-print') {
                loadPrintableItems();
            } else if (targetId === 'panel-processing') {
                loadProcessingItems();
            }
        });
    });
}

// ==== Excel取込タブ ====
function initializeImportTab() {
    const btn = document.getElementById('runExternalScriptBtn');
    if (!btn) return;

    btn.addEventListener('click', async function () {
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.classList.add('opacity-50');
        btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> 実行中...';

        try {
            const dryRunToggle = document.getElementById('externalDryRunToggle');
            const isDryRun = dryRunToggle ? !!dryRunToggle.checked : true;

            if (!isDryRun) {
                const ok = confirm('DBに書き込みを行います。よろしいですか？');
                if (!ok) {
                    btn.disabled = false;
                    btn.classList.remove('opacity-50');
                    btn.innerHTML = originalText;
                    return;
                }
            }

            const res = await fetch(
                `/api/purchase-orders/external-import-test?dry_run=${isDryRun ? 'true' : 'false'}`,
                { method: 'POST' }
            );
            const data = await res.json();
            if (!res.ok) throw new Error(data?.detail || 'APIエラー');

            const r = data?.result || {};
            const modeLabel = isDryRun ? 'DRY-RUN完了' : '実行完了';
            const msg = `${modeLabel}: 対象=${r.total_rows ?? '?'}, 処理=${r.processed ?? '?'}, 作成=${r.created_orders ?? '?'}, スキップ=${r.skipped ?? '?'}`;

            // 結果表示エリアに表示
            const resultArea = document.getElementById('importResultArea');
            const resultContent = document.getElementById('importResultContent');
            if (resultArea && resultContent) {
                resultArea.classList.remove('hidden');
                resultContent.innerHTML = `
                    <p class="font-medium">${modeLabel}</p>
                    <ul class="mt-2 space-y-1">
                        <li>対象行数: ${r.total_rows ?? '?'}</li>
                        <li>処理件数: ${r.processed ?? '?'}</li>
                        <li>作成発注数: ${r.created_orders ?? '?'}</li>
                        <li>スキップ: ${r.skipped ?? '?'}</li>
                    </ul>
                `;
            }

            if (typeof showToast === 'function') {
                showToast(msg, 'success');
                if (!isDryRun) {
                    // 実行時は発注一覧タブに切り替え
                    document.getElementById('tab-orders').click();
                }
            } else {
                alert(msg);
            }
            console.log('Excel取込結果', r);
        } catch (e) {
            const msg = `Excel取込に失敗: ${e?.message || e}`;
            if (typeof showToast === 'function') {
                showToast(msg, 'error');
            } else {
                alert(msg);
            }
            console.error(e);
        } finally {
            btn.disabled = false;
            btn.classList.remove('opacity-50');
            btn.innerHTML = originalText;
        }
    });

    // セット予定表取り込みボタン
    const scheduleBtn = document.getElementById('runScheduleImportBtn');
    if (scheduleBtn) {
        scheduleBtn.addEventListener('click', async function () {
            const originalText = scheduleBtn.innerHTML;
            scheduleBtn.disabled = true;
            scheduleBtn.classList.add('opacity-50');
            scheduleBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> 実行中...';

            try {
                const dryRunToggle = document.getElementById('scheduleDryRunToggle');
                const isDryRun = dryRunToggle ? !!dryRunToggle.checked : true;

                if (!isDryRun) {
                    const ok = confirm('セット予定表からデータを取り込みます。よろしいですか？');
                    if (!ok) {
                        scheduleBtn.disabled = false;
                        scheduleBtn.classList.remove('opacity-50');
                        scheduleBtn.innerHTML = originalText;
                        return;
                    }
                }

                const res = await fetch(
                    `/api/purchase-orders/import-schedule/?dry_run=${isDryRun}`,
                    { method: 'POST' }
                );
                const data = await res.json();
                if (!res.ok) throw new Error(data?.detail || 'APIエラー');

                const r = data?.results || {};
                const modeLabel = isDryRun ? 'DRY-RUN完了' : '取り込み完了';

                // 結果表示エリアに表示
                const resultArea = document.getElementById('scheduleImportResultArea');
                const resultContent = document.getElementById('scheduleImportResultContent');
                if (resultArea && resultContent) {
                    resultArea.classList.remove('hidden');
                    let errorHtml = '';
                    if (r.errors && r.errors.length > 0) {
                        errorHtml = `
                            <div class="mt-3 p-3 bg-warning-amber bg-opacity-10 rounded">
                                <p class="font-medium text-warning-amber mb-2">エラー・警告:</p>
                                <ul class="list-disc list-inside text-xs space-y-1">
                                    ${r.errors.map(err => `<li>${err}</li>`).join('')}
                                </ul>
                            </div>
                        `;
                    }
                    resultContent.innerHTML = `
                        <div class="space-y-2">
                            <p class="font-medium text-success-green">
                                <i class="fas fa-check-circle mr-2"></i>${data.message}
                            </p>
                            <div class="text-sm space-y-1">
                                <p>総件数: ${r.total}件</p>
                                <p>更新: ${r.updated}件</p>
                                <p>スキップ: ${r.skipped}件</p>
                            </div>
                            ${errorHtml}
                        </div>
                    `;
                }

                if (typeof showToast === 'function') {
                    showToast(data.message, 'success');
                    if (!isDryRun) {
                        // 実行時は処理タブに切り替えつつ一覧を更新
                        setTimeout(() => {
                            document.getElementById('tab-processing')?.click();
                            try { loadProcessingItems(); } catch (e) { console.warn('loadProcessingItems error', e); }
                            try { loadReceivingItems(); } catch (e) { console.warn('loadReceivingItems error', e); }
                        }, 1000);
                    }
                } else {
                    alert(data.message);
                }
                console.log('セット予定表取り込み結果', r);
            } catch (e) {
                const msg = `セット予定表取り込みに失敗: ${e?.message || e}`;
                if (typeof showToast === 'function') {
                    showToast(msg, 'error');
                } else {
                    alert(msg);
                }
                console.error(e);
            } finally {
                scheduleBtn.disabled = false;
                scheduleBtn.classList.remove('opacity-50');
                scheduleBtn.innerHTML = originalText;
            }
        });
    }
}

// ==== 発注一覧タブ ====
let currentOrdersPage = 1;
const ordersPageSize = 25;

function initializeOrdersTab() {
    document.getElementById('refreshOrdersBtn')?.addEventListener('click', () => loadOrders(1));
    document.getElementById('resetOrderFiltersBtn')?.addEventListener('click', resetOrderFilters);

    // リアルタイム検索（入力時にdebounceで検索実行）
    document.getElementById('orderNumberFilter')?.addEventListener('input', debounce(() => searchOrders(), 300));
    document.getElementById('orderMaterialFilter')?.addEventListener('input', debounce(() => searchOrders(), 300));
    document.getElementById('orderStatusFilter')?.addEventListener('change', () => searchOrders());
    document.getElementById('orderSupplierFilter')?.addEventListener('input', debounce(() => searchOrders(), 300));
}

async function loadOrders(page = 1) {
    const tableBody = document.getElementById('ordersTableBody');
    const loading = document.getElementById('ordersLoading');
    const empty = document.getElementById('ordersEmpty');

    loading.classList.remove('hidden');
    tableBody.innerHTML = '';
    empty.classList.add('hidden');

    try {
        const response = await fetch(`/api/purchase-orders/?page=${page}&page_size=${ordersPageSize}`);
        const data = await response.json();

        loading.classList.add('hidden');

        if (!data.items || data.items.length === 0) {
            empty.classList.remove('hidden');
            return;
        }

        data.items.forEach(order => {
            const row = createOrderRow(order);
            tableBody.appendChild(row);
        });

        currentOrdersPage = data.page;

        // ページネーション表示
        renderPagination('orders', data.page, data.total_pages, loadOrders);

    } catch (error) {
        loading.classList.add('hidden');
        console.error('発注一覧の読み込みエラー:', error);
        if (typeof showToast === 'function') {
            showToast('発注一覧の読み込みに失敗しました', 'error');
        }
    }
    if (typeof recalculateAmountFromWeight === 'function') {
        recalculateAmountFromWeight();
    }
}

function createOrderRow(order) {
    const row = document.createElement('tr');
    row.className = 'hover:bg-gray-50';

    const statusBadge = getStatusBadge(order.status);
    const orderDate = new Date(order.order_date).toLocaleDateString('ja-JP');
    const deliveryDate = order.expected_delivery_date
        ? new Date(order.expected_delivery_date).toLocaleDateString('ja-JP')
        : '-';
    const firstItem = Array.isArray(order.items) && order.items.length > 0 ? order.items[0] : null;
    const materialSpecDisplay = firstItem
        ? `${firstItem.item_name}${order.items.length > 1 ? ` 他${order.items.length - 1}件` : ''}`
        : '-';

    row.innerHTML = `
        <td class="px-4 py-3 text-sm font-medium text-gray-900">${order.order_number}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${order.supplier}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${orderDate}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${deliveryDate}</td>
        <td class="px-4 py-3">${statusBadge}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${materialSpecDisplay}</td>
        <td class="px-4 py-3">
            <button onclick="viewOrderDetail(${order.id})"
                    class="text-blue-600 hover:text-blue-800 text-sm font-medium">
                詳細
            </button>
        </td>
    `;

    return row;
}

function getStatusBadge(status) {
    const statusMap = {
        pending: { text: '発注済み', class: 'bg-yellow-100 text-yellow-800' },
        partial: { text: '一部入庫', class: 'bg-blue-100 text-blue-800' },
        completed: { text: '完了', class: 'bg-green-100 text-green-800' },
        cancelled: { text: 'キャンセル', class: 'bg-red-100 text-red-800' },
    };

    const statusInfo = statusMap[status] || { text: status, class: 'bg-gray-100 text-gray-800' };

    return `<span class="px-2 py-1 text-xs font-medium rounded-full ${statusInfo.class}">
                ${statusInfo.text}
            </span>`;
}

function searchOrders() {
    const orderNumber = document.getElementById('orderNumberFilter')?.value.toLowerCase() || '';
    const material = document.getElementById('orderMaterialFilter')?.value.toLowerCase() || '';
    const status = document.getElementById('orderStatusFilter')?.value;
    const supplier = document.getElementById('orderSupplierFilter')?.value.toLowerCase() || '';

    const rows = document.querySelectorAll('#ordersTableBody tr');
    let visibleCount = 0;

    rows.forEach(row => {
        const rowOrderNumber = row.cells[0].textContent.toLowerCase();
        const rowSupplier = row.cells[1].textContent.toLowerCase();
        const rowStatus = row.cells[4].textContent.trim();
        const rowMaterial = row.cells[5].textContent.toLowerCase();

        const matchOrderNumber = !orderNumber || rowOrderNumber.includes(orderNumber);
        const matchMaterial = !material || rowMaterial.includes(material);
        const matchSupplier = !supplier || rowSupplier.includes(supplier);
        const matchStatus = !status || rowStatus.includes(getStatusText(status));

        if (matchOrderNumber && matchMaterial && matchSupplier && matchStatus) {
            row.style.display = '';
            visibleCount++;
        } else {
            row.style.display = 'none';
        }
    });
}

function getStatusText(status) {
    const statusMap = {
        pending: '発注済み',
        partial: '一部入庫',
        completed: '完了',
        cancelled: 'キャンセル'
    };
    return statusMap[status] || status;
}

function resetOrderFilters() {
    document.getElementById('orderNumberFilter').value = '';
    document.getElementById('orderMaterialFilter').value = '';
    document.getElementById('orderStatusFilter').value = '';
    document.getElementById('orderSupplierFilter').value = '';
    searchOrders();
}

async function viewOrderDetail(orderId) {
    try {
        const response = await fetch(`/api/purchase-orders/${orderId}`);
        const order = await response.json();

        // 簡易モーダルで詳細表示
        const orderDate = new Date(order.order_date).toLocaleDateString('ja-JP');
        const deliveryDate = order.expected_delivery_date
            ? new Date(order.expected_delivery_date).toLocaleDateString('ja-JP')
            : '-';
        const firstItem = Array.isArray(order.items) && order.items.length > 0 ? order.items[0] : null;

        let orderDisplay = '';
        if (firstItem) {
            if (firstItem.order_type === 'weight') {
                orderDisplay = `${firstItem.ordered_weight_kg ?? '-'}kg`;
            } else {
                orderDisplay = `${firstItem.ordered_quantity ?? '-'}本`;
            }
        }

        const detailHtml = `
            <div class="space-y-4">
                <div>
                    <h3 class="text-lg font-medium text-gray-900 mb-4">発注概要</h3>
                    <dl class="grid grid-cols-2 gap-4">
                        <div>
                            <dt class="text-sm font-medium text-gray-500">発注番号</dt>
                            <dd class="text-sm text-gray-900 mt-1">${order.order_number}</dd>
                        </div>
                        <div>
                            <dt class="text-sm font-medium text-gray-500">仕入先</dt>
                            <dd class="text-sm text-gray-900 mt-1">${order.supplier}</dd>
                        </div>
                        <div>
                            <dt class="text-sm font-medium text-gray-500">発注日</dt>
                            <dd class="text-sm text-gray-900 mt-1">${orderDate}</dd>
                        </div>
                        <div>
                            <dt class="text-sm font-medium text-gray-500">納期予定日</dt>
                            <dd class="text-sm text-gray-900 mt-1">${deliveryDate}</dd>
                        </div>
                        <div>
                            <dt class="text-sm font-medium text-gray-500">状態</dt>
                            <dd class="text-sm mt-1">${getStatusBadge(order.status)}</dd>
                        </div>
                    </dl>
                </div>
                
                <div>
                    <h3 class="text-lg font-medium text-gray-900 mb-3">発注内容</h3>
                    <div class="bg-gray-50 rounded-lg p-4">
                        <div class="text-sm text-gray-900 font-medium mb-1">${firstItem?.item_name || '-'}</div>
                        <div class="text-sm text-gray-700">
                            ${orderDisplay}
                            <span class="text-xs text-gray-500 ml-2">
                                ${firstItem?.order_type === 'weight' ? '重量指定' : '本数指定'}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // アラートまたはカスタムモーダルで表示
        if (typeof showToast === 'function') {
            // カスタムモーダルがあれば使用
            showDetailModal('発注詳細', detailHtml);
        } else {
            // フォールバック: シンプルなアラート
            alert(`発注番号: ${order.order_number}\n仕入先: ${order.supplier}\n発注日: ${orderDate}`);
        }
    } catch (error) {
        console.error('発注詳細取得エラー:', error);
        if (typeof showToast === 'function') {
            showToast('発注詳細の取得に失敗しました', 'error');
        }
    }
}

function showDetailModal(title, content) {
    // 簡易モーダルを動的に作成
    const modalId = 'orderDetailModal';
    let modal = document.getElementById(modalId);

    if (!modal) {
        modal = document.createElement('div');
        modal.id = modalId;
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4';
        modal.innerHTML = `
            <div class="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                <div class="p-6 border-b flex justify-between items-center">
                    <h2 class="text-xl font-semibold text-gray-900">${title}</h2>
                    <button onclick="closeDetailModal()" class="text-gray-400 hover:text-gray-600">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
                <div class="p-6" id="orderDetailContent"></div>
            </div>
        `;
        document.body.appendChild(modal);

        // ESCキーで閉じる
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
                closeDetailModal();
            }
        });

        // 背景クリックで閉じる
        modal.addEventListener('click', function (e) {
            if (e.target === modal) {
                closeDetailModal();
            }
        });
    }

    document.getElementById('orderDetailContent').innerHTML = content;
    modal.classList.remove('hidden');
}

function closeDetailModal() {
    const modal = document.getElementById('orderDetailModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// ==== 入庫確認タブ ====
function initializeReceivingTab() {
    document.getElementById('refreshReceivingBtn')?.addEventListener('click', () => loadReceivingItems(1));
    document.getElementById('resetReceivingFiltersBtn')?.addEventListener('click', resetReceivingFilters);
    document.getElementById('includeInspectedFilter')?.addEventListener('change', () => loadReceivingItems(1));

    // リアルタイム検索（入力時にdebounceで検索実行）
    document.getElementById('receivingOrderNumberFilter')?.addEventListener('input', debounce(() => searchReceivingItems(), 300));
    document.getElementById('receivingSupplierFilter')?.addEventListener('input', debounce(() => searchReceivingItems(), 300));
    document.getElementById('receivingMaterialFilter')?.addEventListener('input', debounce(() => searchReceivingItems(), 300));

    // 手入力で入庫ボタン
    document.getElementById('manualReceiveBtn')?.addEventListener('click', showManualReceiveModal);

    // 手入力用入庫確認モーダル
    document.getElementById('closeManualReceiveModal')?.addEventListener('click', hideManualReceiveModal);
    document.getElementById('cancelManualReceive')?.addEventListener('click', hideManualReceiveModal);
    document.getElementById('manualReceiveForm')?.addEventListener('submit', handleManualReceive);

    // 入庫確認モーダル
    document.getElementById('closeReceiveModal')?.addEventListener('click', hideReceiveModal);
    document.getElementById('cancelReceive')?.addEventListener('click', hideReceiveModal);
    document.getElementById('receiveForm')?.addEventListener('submit', handleReceive);

    // フォーム内のEnterキー制御（submitボタン以外でEnter押下時は送信を防ぐ）
    const receiveFormElement = document.getElementById('receiveForm');
    if (receiveFormElement) {
        receiveFormElement.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                // submitボタン以外でEnterキーが押された場合は送信を防ぐ
                if (e.target.type !== 'submit' && e.target.tagName !== 'BUTTON') {
                    e.preventDefault();
                }
            }
        });
    }

    // モーダル背景クリックで閉じる
    const receiveModal = document.getElementById('receiveModal');
    if (receiveModal) {
        receiveModal.addEventListener('click', function (e) {
            if (e.target === receiveModal || e.target.classList.contains('modal-overlay')) {
                hideReceiveModal();
            }
        });
    }

    // ESCキーでモーダルを閉じる
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            const receiveModal = document.getElementById('receiveModal');
            if (receiveModal && !receiveModal.classList.contains('hidden')) {
                hideReceiveModal();
            }
        }
    });
}

let receivingAllItems = [];
let currentReceivingPage = 1;
const receivingPageSize = 25;

async function loadReceivingItems(page = 1) {
    page = Number.isFinite(page) ? page : 1;
    const tableBody = document.getElementById('receivingItemsTableBody');
    const loading = document.getElementById('receivingLoading');
    const empty = document.getElementById('receivingEmpty');

    loading.classList.remove('hidden');
    tableBody.innerHTML = '';
    empty.classList.add('hidden');

    try {
        const includeInspected = document.getElementById('includeInspectedFilter')?.checked ? 'true' : 'false';
        const response = await fetch(`/api/purchase-orders/pending-or-inspection/items/?include_inspected=${includeInspected}`);
        const items = await response.json();

        loading.classList.add('hidden');

        if (items.length === 0) {
            empty.classList.remove('hidden');
            receivingAllItems = [];
            return;
        }

        // 発注情報も取得（N+1問題対策：一括取得）
        const orderIds = [...new Set(items.map(i => i.purchase_order_id))];
        const ordersMap = new Map();

        await Promise.all(
            orderIds.map(async (orderId) => {
                try {
                    const orderResponse = await fetch(`/api/purchase-orders/${orderId}`);
                    if (orderResponse.ok) {
                        const order = await orderResponse.json();
                        ordersMap.set(orderId, order);
                    }
                } catch (error) {
                    console.error('発注情報取得エラー:', error);
                }
            })
        );

        // 各アイテムに発注情報を紐付け
        const itemsWithOrders = items.map(item => ({
            ...item,
            purchase_order: ordersMap.get(item.purchase_order_id) || null
        }));

        // 全アイテムを保存
        receivingAllItems = itemsWithOrders;

        // ページネーション処理
        const totalPages = Math.ceil(receivingAllItems.length / receivingPageSize);
        currentReceivingPage = Math.min(page, totalPages);
        const startIndex = (currentReceivingPage - 1) * receivingPageSize;
        const endIndex = startIndex + receivingPageSize;
        const pageItems = receivingAllItems.slice(startIndex, endIndex);

        pageItems.forEach(item => {
            const row = createReceivingItemRow(item);
            tableBody.appendChild(row);
        });

        // ページネーション表示
        renderPagination('receiving', currentReceivingPage, totalPages, loadReceivingItems);

    } catch (error) {
        loading.classList.add('hidden');
        console.error('入庫待ちアイテム読み込みエラー:', error);
        if (typeof showToast === 'function') {
            showToast('入庫待ちアイテムの読み込みに失敗しました', 'error');
        }
    }
}

function createReceivingItemRow(item) {
    const row = document.createElement('tr');
    row.className = 'hover:bg-gray-50';

    const orderNumber = item.purchase_order ? item.purchase_order.order_number : '-';
    const supplier = item.purchase_order ? item.purchase_order.supplier : '-';
    const orderDate = (item.purchase_order && item.purchase_order.order_date)
        ? new Date(item.purchase_order.order_date).toLocaleDateString('ja-JP')
        : '-';
    const expectedDate = (item.purchase_order && item.purchase_order.expected_delivery_date)
        ? new Date(item.purchase_order.expected_delivery_date).toLocaleDateString('ja-JP')
        : '-';

    const isReceived = String(item.status).toUpperCase() === 'RECEIVED';
    const receivingBtnLabel = isReceived ? '再編集' : '入庫確認';
    const receivingBtnClasses = isReceived
        ? 'bg-amber-500 text-white px-3 py-1 rounded text-sm hover:bg-amber-600'
        : 'bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700';

    // 検品状態バッジ
    let inspectionText = '-';
    let inspectionClass = 'bg-gray-100 text-gray-600';
    if (isReceived) {
        const statusUpper = String(item.inspection_status || 'PENDING').toUpperCase();
        if (statusUpper === 'PASSED') {
            inspectionText = '合格';
            inspectionClass = 'bg-green-100 text-green-700';
        } else if (statusUpper === 'FAILED') {
            inspectionText = '不合格';
            inspectionClass = 'bg-red-100 text-red-700';
        } else {
            inspectionText = '未検品';
            inspectionClass = 'bg-amber-100 text-amber-700';
        }
    }

    row.innerHTML = `
        <td class="px-4 py-3 text-sm font-medium text-gray-900">${orderNumber}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${supplier}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${orderDate}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${expectedDate}</td>
    <td class="px-4 py-3 text-sm text-gray-600">${item.item_name}</td>
    <td class="px-4 py-3 text-sm text-gray-600">${getOrderDisplayText(item)}</td>
    <td class="px-4 py-3 text-sm text-gray-600">${formatDateToJP(item.set_scheduled_date)}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${item.machine_no || '-'}</td>
        <td class="px-4 py-3">
            <span class="px-2 py-1 rounded-full text-xs font-medium ${inspectionClass}">${inspectionText}</span>
        </td>
        <td class="px-4 py-3">
            <button onclick="showReceiveModal(${item.id})" class="${receivingBtnClasses}">
                ${receivingBtnLabel}
            </button>
        </td>
    `;

    return row;
}

function getOrderDisplayText(item) {
    if (item.order_type === 'weight') {
        return `${item.ordered_weight_kg}kg`;
    } else {
        return `${item.ordered_quantity}本`;
    }
}

function searchReceivingItems() {
    const supplier = document.getElementById('receivingSupplierFilter')?.value?.toLowerCase() || '';
    const orderNumber = document.getElementById('receivingOrderNumberFilter')?.value?.toLowerCase() || '';
    const material = document.getElementById('receivingMaterialFilter')?.value?.toLowerCase() || '';

    const rows = document.querySelectorAll('#receivingItemsTableBody tr');
    let visibleCount = 0;

    rows.forEach(row => {
        const rowSupplier = row.cells[1]?.textContent?.toLowerCase() || '';
        const rowOrderNumber = row.cells[0]?.textContent?.toLowerCase() || '';
        const rowMaterial = row.cells[4]?.textContent?.toLowerCase() || '';

        const matchSupplier = !supplier || rowSupplier.includes(supplier);
        const matchOrderNumber = !orderNumber || rowOrderNumber.includes(orderNumber);
        const matchMaterial = !material || rowMaterial.includes(material);

        if (matchSupplier && matchOrderNumber && matchMaterial) {
            row.style.display = '';
            visibleCount++;
        } else {
            row.style.display = 'none';
        }
    });
}

function resetReceivingFilters() {
    document.getElementById('receivingOrderNumberFilter').value = '';
    document.getElementById('receivingSupplierFilter').value = '';
    document.getElementById('receivingMaterialFilter').value = '';
    searchReceivingItems();
}

// 入庫確認モーダル（receiving.jsから移植・簡略化）
async function showReceiveModal(itemId) {
    try {
        const response = await fetch(`/api/purchase-orders/pending-or-inspection/items/`);
        const items = await response.json();
        const item = items.find(i => i.id === itemId);

        if (!item) {
            if (typeof showToast === 'function') {
                showToast('アイテムが見つかりません', 'error');
            }
            return;
        }

        const orderResponse = await fetch(`/api/purchase-orders/${item.purchase_order_id}`);
        const order = await orderResponse.json();

        document.getElementById('receiveItemId').value = itemId;

        // 比重プリセット一覧を読み込み
        await loadDensityPresets();

        const itemInfo = document.getElementById('itemInfo');
        itemInfo.innerHTML = `
            <div>
                <dt class="font-medium text-gray-500">発注番号</dt>
                <dd class="text-gray-900">${order.order_number}</dd>
            </div>
            <div>
                <dt class="font-medium text-gray-500">仕入先</dt>
                <dd class="text-gray-900">${order.supplier}</dd>
            </div>
            <div class="md:col-span-2">
                <dt class="font-medium text-gray-500">材料仕様（発注品名）</dt>
                <dd class="text-gray-900 mt-1">${item.item_name}</dd>
            </div>
            <div>
                <dt class="font-medium text-gray-500">発注数量/重量</dt>
                <dd class="text-gray-900">${getOrderDisplayText(item)}</dd>
            </div>
        `;

        // 単価・金額の初期値設定
        const unitPriceInput = document.getElementById('unitPriceInput');
        const amountInput = document.getElementById('amountInput');
        if (unitPriceInput && item.unit_price !== null && item.unit_price !== undefined) {
            unitPriceInput.value = item.unit_price;
        } else if (unitPriceInput) {
            unitPriceInput.value = '';
        }
        if (amountInput && item.amount !== null && item.amount !== undefined) {
            amountInput.value = item.amount;
        } else if (amountInput) {
            amountInput.value = '';
        }

        // 単価（円/kg）入力時に、重量ベースで金額を自動計算
        if (unitPriceInput) {
            unitPriceInput.addEventListener('input', recalculateAmountFromWeight);
        }

        // 受入済みの再編集時は、登録時の値（最新ロット）をそのまま自動入力
        let previousFilled = false;
        try {
            const isReceived = String(item.status).toUpperCase() === 'RECEIVED';
            if (isReceived) {
                const prevRes = await fetch(`/api/purchase-orders/items/${itemId}/receive/previous/`);
                if (prevRes.ok) {
                    const prev = await prevRes.json();

                    // 入力要素
                    const diameterCalcInput = document.getElementById('diameterCalcInput');
                    const shapeCalcSelect = document.getElementById('shapeCalcSelect');
                    const densityField = document.getElementById('densityInput');
                    const lengthField = document.querySelector('input[name="length_mm"]');
                    const receivedDateField = document.querySelector('input[name="received_date"]');

                    // 計算用パラメータ
                    if (diameterCalcInput && typeof prev.diameter_mm === 'number') diameterCalcInput.value = prev.diameter_mm;
                    if (shapeCalcSelect && prev.shape) shapeCalcSelect.value = prev.shape;
                    if (densityField && typeof prev.density === 'number') densityField.value = prev.density;

                    // 再編集時：比重プリセット選択を復元（値一致で選択）
                    const densityPresetSelect = document.getElementById('densityPresetSelect');
                    if (densityPresetSelect && typeof prev.density === 'number') {
                        const target = prev.density;
                        for (const opt of densityPresetSelect.options) {
                            if (!opt.value) continue;
                            const val = parseFloat(opt.value);
                            if (Number.isFinite(val) && Math.abs(val - target) < 1e-6) {
                                densityPresetSelect.value = opt.value;
                                break;
                            }
                        }
                    }
                    if (lengthField && typeof prev.length_mm === 'number') lengthField.value = prev.length_mm;

                    // 入荷日
                    if (receivedDateField && prev.received_date) {
                        const d = new Date(prev.received_date);
                        const ymd = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
                        receivedDateField.value = ymd;
                    }

                    // 購入月
                    const purchaseMonthField = document.querySelector('input[name="purchase_month"]');
                    if (purchaseMonthField && prev.purchase_month) {
                        purchaseMonthField.value = prev.purchase_month;
                    }

                    // ロット情報（全ロットを復元）
                    clearLotRows();

                    if (Array.isArray(prev.lots) && prev.lots.length > 0) {
                        // 複数ロットを復元
                        prev.lots.forEach(lot => {
                            addLotRow(
                                lot.received_quantity || null,
                                lot.received_weight_kg || null,
                                lot.lot_number || '',
                                lot.location_id ? String(lot.location_id) : '',
                                lot.notes || ''
                            );
                        });
                    } else {
                        // 旧フォーマット対応は不要（新スキーマのみサポート）
                        addLotRow(
                            prev.received_quantity || null,
                            prev.received_weight_kg || null,
                            prev.lot_number || '',
                            prev.location_id ? String(prev.location_id) : '',
                            prev.notes || ''
                        );
                    }

                    previousFilled = true;

                    // 再編集フラグをフォームに設定（handleReceiveでPUT/POSTを切り替えるため）
                    const receiveForm = document.getElementById('receiveForm');
                    if (receiveForm) {
                        let isEditInput = receiveForm.querySelector('input[name="is_edit"]');
                        if (!isEditInput) {
                            isEditInput = document.createElement('input');
                            isEditInput.type = 'hidden';
                            isEditInput.name = 'is_edit';
                            receiveForm.appendChild(isEditInput);
                        }
                        isEditInput.value = 'true';

                        // 既存のロット番号リストを保存（JSON文字列として）
                        let prevLotsInput = receiveForm.querySelector('input[name="previous_lot_numbers"]');
                        if (!prevLotsInput) {
                            prevLotsInput = document.createElement('input');
                            prevLotsInput.type = 'hidden';
                            prevLotsInput.name = 'previous_lot_numbers';
                            receiveForm.appendChild(prevLotsInput);
                        }

                        // 既存ロット番号の配列を作成
                        const existingLotNumbers = [];
                        if (Array.isArray(prev.lots)) {
                            prev.lots.forEach(lot => {
                                if (lot.lot_number) {
                                    existingLotNumbers.push(lot.lot_number);
                                }
                            });
                        } else if (prev.lot_number) {
                            existingLotNumbers.push(prev.lot_number);
                        }

                        prevLotsInput.value = JSON.stringify(existingLotNumbers);
                    }
                }
            }
        } catch (error) {
            console.warn('再編集用自動入力に失敗しました', error);
        }

        // 入荷日のデフォルト（未設定時のみ本日に設定）
        const receivedDateField = document.querySelector('input[name="received_date"]');
        if (receivedDateField && !receivedDateField.value) {
            const now = new Date();
            const localDate = now.getFullYear() + '-' +
                String(now.getMonth() + 1).padStart(2, '0') + '-' +
                String(now.getDate()).padStart(2, '0');
            receivedDateField.value = localDate;
        }

        // 計算用パラメータの要素を取得
        const diameterCalcInput = document.getElementById('diameterCalcInput');
        const shapeCalcSelect = document.getElementById('shapeCalcSelect');
        const densityInput = document.getElementById('densityInput');
        const lengthInput = document.querySelector('input[name="length_mm"]');

        // 新規入庫時に径・形状を自動抽出（再編集時はスキップ）
        if (!previousFilled && item.item_name) {
            // 径を自動抽出
            const extractedDiameter = extractDiameterFromName(item.item_name);
            if (extractedDiameter && diameterCalcInput) {
                diameterCalcInput.value = extractedDiameter;
            }

            // 形状を自動判定
            const detectedShape = detectShapeFromName(item.item_name);
            if (detectedShape && shapeCalcSelect) {
                shapeCalcSelect.value = detectedShape;
            }
        }

        // 長さのデフォルト値（未設定時のみ 2500）
        if (lengthInput && !lengthInput.value) {
            lengthInput.value = 2500;
        }

        // 発注数量・発注タイプを保存
        currentOrderType = item.order_type || 'quantity';
        currentOrderedQuantity = item.order_type === 'weight' ? 0 : item.ordered_quantity;
        document.getElementById('orderedQuantity').textContent = currentOrderedQuantity > 0 ? currentOrderedQuantity : '-';

        // ロット行を初期化（未復元時のみ発注情報で初期化）
        if (!previousFilled) {
            clearLotRows();
            if (item.order_type === 'weight' && item.ordered_weight_kg) {
                addLotRow(null, item.ordered_weight_kg);
            } else if (item.ordered_quantity) {
                addLotRow(item.ordered_quantity, null);
            } else {
                addLotRow();
            }
        }

        // addLotBtnのイベントリスナーを設定
        const addLotBtn = document.getElementById('addLotBtn');
        if (addLotBtn) {
            addLotBtn.onclick = addLotRow;
        }

        // 計算用パラメータ変更時に合計を更新（イベントリスナーの重複を防ぐ）
        if (diameterCalcInput) {
            diameterCalcInput.removeEventListener('input', updateTotalQuantity);
            diameterCalcInput.addEventListener('input', updateTotalQuantity);
        }
        if (shapeCalcSelect) {
            shapeCalcSelect.removeEventListener('change', updateTotalQuantity);
            shapeCalcSelect.addEventListener('change', updateTotalQuantity);
        }
        if (densityInput) {
            densityInput.removeEventListener('input', updateTotalQuantity);
            densityInput.addEventListener('input', updateTotalQuantity);
        }
        if (lengthInput) {
            lengthInput.removeEventListener('input', updateTotalQuantity);
            lengthInput.addEventListener('input', updateTotalQuantity);
        }

        // 入荷日変更時に購入月を自動設定
        setupPurchaseMonthAutoUpdate();

        document.getElementById('receiveModal').classList.remove('hidden');
        // 初期表示時に合計・参考値を更新
        if (typeof updateTotalQuantity === 'function') {
            updateTotalQuantity();
        }
    } catch (error) {
        console.error('入庫確認モーダル表示エラー:', error);
        if (typeof showToast === 'function') {
            showToast('入庫確認画面の表示に失敗しました', 'error');
        }
    }
}

function hideReceiveModal() {
    document.getElementById('receiveModal').classList.add('hidden');
    document.getElementById('receiveForm').reset();

    // 比重プリセット選択をリセット
    const densityPresetSelect = document.getElementById('densityPresetSelect');
    if (densityPresetSelect) {
        densityPresetSelect.value = '';
    }

    // ロット行をクリア
    clearLotRows();

    // 発注数量をリセット
    currentOrderedQuantity = 0;

    // 二重送信防止フラグをリセット
    isSubmittingReceive = false;

    // 送信ボタンの状態をリセット
    const submitButton = document.querySelector('#receiveForm button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = false;
        submitButton.innerHTML = '入庫確定';
    }
}

// 購入月の自動設定
function setupPurchaseMonthAutoUpdate() {
    const receivedDateInput = document.getElementById('receivedDateInput');
    const purchaseMonthInput = document.getElementById('purchaseMonthInput');

    if (!receivedDateInput || !purchaseMonthInput) return;

    // 入荷日変更時に購入月を自動設定
    receivedDateInput.removeEventListener('change', updatePurchaseMonth);
    receivedDateInput.addEventListener('change', updatePurchaseMonth);

    // 初回設定（入荷日が既にある場合）
    if (receivedDateInput.value) {
        updatePurchaseMonth();
    }
}

function updatePurchaseMonth() {
    const receivedDateInput = document.getElementById('receivedDateInput');
    const purchaseMonthInput = document.getElementById('purchaseMonthInput');

    if (!receivedDateInput || !purchaseMonthInput || !receivedDateInput.value) return;

    const date = new Date(receivedDateInput.value);
    const year = date.getFullYear() % 100; // 下2桁
    const month = date.getMonth() + 1; // 1-12

    const yymm = String(year).padStart(2, '0') + String(month).padStart(2, '0');
    purchaseMonthInput.value = yymm;
}

// 換算機能のイベントリスナーを設定
function setupConversionListeners() {
    const quantityInput = document.getElementById('quantityInput');
    const weightInput = document.getElementById('weightInput');
    const diameterInput = document.querySelector('input[name="diameter_input"]');
    const densityInput = document.getElementById('densityInput');
    const lengthInput = document.querySelector('input[name="length_mm"]');
    const inputMethodRadios = document.querySelectorAll('input[name="input_method"]');

    // 本数入力時：重量をクリア、本数モードに切り替え
    if (quantityInput) {
        quantityInput.oninput = function () {
            if (this.value) {
                weightInput.value = '';
                const quantityRadio = document.querySelector('input[name="input_method"][value="quantity"]');
                if (quantityRadio) quantityRadio.checked = true;
            }
            updateConversion();
        };
    }

    // 重量入力時：本数をクリア、重量モードに切り替え
    if (weightInput) {
        weightInput.oninput = function () {
            if (this.value) {
                quantityInput.value = '';
                const weightRadio = document.querySelector('input[name="input_method"][value="weight"]');
                if (weightRadio) weightRadio.checked = true;
            }
            updateConversion();
        };
    }

    // 径・比重・長さ変更時に換算を更新
    if (diameterInput) diameterInput.addEventListener('input', updateConversion);
    if (densityInput) densityInput.addEventListener('input', updateConversion);
    if (lengthInput) lengthInput.addEventListener('input', updateConversion);

    // 入力方式切り替え時
    inputMethodRadios.forEach(radio => {
        radio.onchange = function () {
            if (this.value === 'quantity') {
                if (quantityInput) quantityInput.focus();
                if (weightInput) weightInput.value = '';
            } else {
                if (weightInput) weightInput.focus();
                if (quantityInput) quantityInput.value = '';
            }
            updateConversion();
        };
    });
}

// 比重プリセット一覧を読み込み
async function loadDensityPresets() {
    try {
        const response = await fetch('/api/density-presets/?is_active=true&limit=100');
        if (!response.ok) {
            console.warn('比重プリセットの取得に失敗しました');
            return;
        }

        const presets = await response.json();
        const selectElement = document.getElementById('densityPresetSelect');

        if (!selectElement) return;

        // 既存のオプションをクリア（最初のプレースホルダーは残す）
        selectElement.innerHTML = '<option value="">プリセットから選択</option>';

        // プリセットを追加
        presets.forEach(preset => {
            const option = document.createElement('option');
            option.value = preset.density;
            option.textContent = `${preset.name} (${preset.density})`;
            option.dataset.name = preset.name;
            selectElement.appendChild(option);
        });

        // 選択イベントを設定（入庫確認モーダル用）
        selectElement.onchange = function () {
            const densityInput = document.getElementById('densityInput');
            if (this.value && densityInput) {
                densityInput.value = this.value;

                // 選択したプリセット名をトーストで通知
                const selectedOption = this.options[this.selectedIndex];
                if (selectedOption && selectedOption.dataset.name && typeof showToast === 'function') {
                    showToast(`比重プリセット「${selectedOption.dataset.name}」を適用しました`, 'success');
                }

                // 合計を更新（入庫確認モーダル用）
                if (typeof updateTotalQuantity === 'function') {
                    updateTotalQuantity();
                }
            }
        };

    } catch (error) {
        console.error('比重プリセット読み込みエラー:', error);
    }
}

// 送信中フラグ（二重送信防止用）
let isSubmittingReceive = false;

async function handleReceive(event) {
    event.preventDefault();

    // 二重送信防止：送信中の場合は処理をスキップ
    if (isSubmittingReceive) {
        console.log('入庫確認処理中のため、重複送信を防止しました');
        return;
    }

    // 送信ボタンを取得して無効化
    const submitButton = event.target.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>処理中...';
    }

    // 送信中フラグを設定
    isSubmittingReceive = true;

    try {
        const formData = new FormData(event.target);
        const itemId = formData.get('item_id');

        // 再編集フラグ（既存ロットの更新時はPUTを使用）
        const isEdit = (formData.get('is_edit') || '') === 'true';

    // 既存のロット番号リストを取得
    const removedLotNumbers = [];
    let previousLotNumbers = [];
    try {
        const prevLotsStr = formData.get('previous_lot_numbers');
        console.log('previous_lot_numbers (raw):', prevLotsStr); // デバッグ
        if (prevLotsStr) {
            previousLotNumbers = JSON.parse(prevLotsStr);
        }
    } catch (e) {
        console.warn('既存ロット番号の解析に失敗:', e);
    }

    console.log('isEdit:', isEdit); // デバッグ
    console.log('previousLotNumbers:', previousLotNumbers); // デバッグ

    // 計算用パラメータを取得
    const diameter_mm = parseFloat(formData.get('diameter_mm'));
    const shape = formData.get('shape');
    const density = parseFloat(formData.get('density'));
    const length_mm = parseInt(formData.get('length_mm'));

    // バリデーション
    if (isNaN(diameter_mm) || diameter_mm <= 0) {
        if (typeof showToast === 'function') {
            showToast('径を正しく入力してください', 'error');
        }
        return;
    }

    if (!shape || !['round', 'hexagon', 'square'].includes(shape)) {
        if (typeof showToast === 'function') {
            showToast('形状を選択してください', 'error');
        }
        return;
    }

    if (isNaN(density) || density <= 0) {
        if (typeof showToast === 'function') {
            showToast('比重を正しく入力してください', 'error');
        }
        return;
    }

    if (isNaN(length_mm) || length_mm <= 0) {
        if (typeof showToast === 'function') {
            showToast('長さを正しく入力してください', 'error');
        }
        return;
    }

    // 購入月を取得
    const purchaseMonth = formData.get('purchase_month');
    if (!purchaseMonth || !/^\d{4}$/.test(purchaseMonth)) {
        if (typeof showToast === 'function') {
            showToast('購入月をYYMM形式（例: 2501）で入力してください', 'error');
        }
        return;
    }

    // 単価・金額を取得
    const unitPrice = formData.get('unit_price');
    const amount = formData.get('amount');

    // 共通入庫データ
    const commonMaterialData = {
        diameter_mm: diameter_mm,
        shape: shape,
        density: density,
        length_mm: length_mm,
        received_date: formData.get('received_date') + 'T00:00:00'
    };

    // 単価・金額を追加（値が入力されている場合のみ）
    if (unitPrice && unitPrice.trim() !== '' && !isNaN(parseFloat(unitPrice))) {
        commonMaterialData.unit_price = parseFloat(unitPrice);
    }
    if (amount && amount.trim() !== '' && !isNaN(parseFloat(amount))) {
        commonMaterialData.amount = parseFloat(amount);
    }

    // 各ロット情報を収集（DOM要素から直接取得）
    const lots = [];
    for (let i = 1; i <= lotRowCounter; i++) {
        const lotRow = document.getElementById(`lot-row-${i}`);
        if (!lotRow) continue; // 削除されたロット行はスキップ

        // DOM要素から直接値を取得（FormDataではなく）
        const lotNumberInput = lotRow.querySelector(`input[name="lot_number_${i}"]`);
        const quantityInput = lotRow.querySelector(`input[name="lot_quantity_${i}"]`);
        const weightInput = lotRow.querySelector(`input[name="lot_weight_${i}"]`);
        const locationElement = lotRow.querySelector(`select[name="lot_location_${i}"]`) || lotRow.querySelector(`input[name="lot_location_${i}"]`);
        const notesInput = lotRow.querySelector(`input[name="lot_notes_${i}"]`);

        const lotNumber = lotNumberInput?.value || '';
        const quantityStr = quantityInput?.value || '';
        const weightStr = weightInput?.value || '';
        const location = locationElement?.value || '';
        const lotNotes = notesInput?.value || '';

        console.log(`ロット ${i}:`, { lotNumber, quantityStr, weightStr, location, lotNotes }); // デバッグ

        if (!lotNumber || lotNumber.trim() === '') {
            if (typeof showToast === 'function') {
                showToast(`ロット ${i}: ロット番号は必須です`, 'error');
            }
            return;
        }

        // 空文字列をnullに変換
        const quantity = quantityStr && quantityStr.trim() !== '' ? quantityStr : null;
        const weight = weightStr && weightStr.trim() !== '' ? weightStr : null;

        // 本数・重量のどちらか一方でも入力が必要（両方可）
        if (!quantity && !weight) {
            if (typeof showToast === 'function') {
                showToast(`ロット ${i}: 本数または重量のいずれかを入力してください`, 'error');
            }
            return;
        }

        const lotData = {
            lot_number: lotNumber.trim(),
            location_id: location && location.trim() !== '' ? parseInt(location) : null,
            purchase_month: purchaseMonth,
            notes: lotNotes.trim() || null
        };

        if (quantity) {
            lotData.received_quantity = parseInt(quantity, 10);
        }
        if (weight) {
            lotData.received_weight_kg = parseFloat(weight);
        }

        lots.push(lotData);
    }

    // 削除されたロット番号を特定（既存ロットリストとの差分）
    previousLotNumbers.forEach(prevLotNumber => {
        const stillExists = lots.some(lot => lot.lot_number === prevLotNumber);
        if (!stillExists) {
            removedLotNumbers.push(prevLotNumber);
        }
    });

    if (lots.length === 0) {
        if (typeof showToast === 'function') {
            showToast('少なくとも1つのロットを入力してください', 'error');
        }
        return;
    }

    // 重量基準のため合計本数チェックは行いません

    // 各ロットに対してAPI呼び出し
    try {
        let appliedCount = 0;

        for (const lot of lots) {
            const receiveData = {
                ...commonMaterialData,
                lot_number: lot.lot_number,
                purchase_month: lot.purchase_month,  // 購入月を追加
                notes: lot.notes  // 備考を追加
            };

            // 入力された本数・重量をそのまま送信
            if (typeof lot.received_quantity === 'number') {
                receiveData.received_quantity = lot.received_quantity;
            }
            if (typeof lot.received_weight_kg === 'number') {
                receiveData.received_weight_kg = lot.received_weight_kg;
            }

            if (lot.location_id) {
                receiveData.location_id = lot.location_id;
            }

            console.log('送信データ:', receiveData); // デバッグ

            // 再編集（既存ロットの更新）かどうかを判定
            // 既存のロット番号リストに含まれている場合はPUT、新規の場合はPOST
            const isUpdatingExisting = isEdit && previousLotNumbers.includes(lot.lot_number);
            const methodToUse = isUpdatingExisting ? 'PUT' : 'POST';

            console.log(`ロット ${lot.lot_number}: ${methodToUse} (isEdit=${isEdit}, 既存=${isUpdatingExisting})`); // デバッグ

            const response = await fetch(`/api/purchase-orders/items/${itemId}/receive/`, {
                method: methodToUse,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(receiveData)
            });

            if (!response.ok) {
                let errorMsg;
                // レスポンスボディを一度テキストとして読み込む
                const responseText = await response.text();
                console.error('サーバーエラー（テキスト）:', responseText);

                try {
                    // テキストをJSONとしてパース
                    const error = JSON.parse(responseText);
                    errorMsg = error.detail || JSON.stringify(error);
                } catch (e) {
                    // JSONパースに失敗した場合はテキストをそのまま使用
                    errorMsg = responseText.substring(0, 200) || `サーバーエラー (${response.status})`;
                }
                throw new Error(`ロット ${lot.lot_number}: ${errorMsg}`);
            }

            appliedCount++;
        }

        let deletedCount = 0;
        const deletionErrors = [];

        for (const deletedLotNumber of removedLotNumbers) {
            try {
                const deleteRes = await fetch(`/api/purchase-orders/items/${itemId}/receive/${encodeURIComponent(deletedLotNumber)}/`, {
                    method: 'DELETE'
                });

                if (!deleteRes.ok) {
                    const deleteText = await deleteRes.text();
                    let deleteMsg = deleteText;
                    try {
                        const parsed = JSON.parse(deleteText);
                        deleteMsg = parsed.detail || deleteMsg;
                    } catch (parseErr) {
                        deleteMsg = deleteMsg?.substring(0, 200) || `ステータス ${deleteRes.status}`;
                    }
                    deletionErrors.push(`ロット ${deletedLotNumber}: ${deleteMsg}`);
                } else {
                    deletedCount++;
                }
            } catch (deleteError) {
                deletionErrors.push(`ロット ${deletedLotNumber}: ${deleteError.message || deleteError}`);
            }
        }

        if (typeof showToast === 'function') {
            let message = `${appliedCount}件のロットを登録・更新しました`;
            if (removedLotNumbers.length > 0) {
                message += `（削除 ${deletedCount}/${removedLotNumbers.length}件）`;
            }

            if (deletionErrors.length > 0) {
                showToast(`${message}。一部ロットの削除に失敗しました。`, 'warning');
                deletionErrors.slice(0, 3).forEach(errMsg => showToast(errMsg, 'error'));
            } else {
                showToast(message, 'success');
            }
        }
        hideReceiveModal();
        loadReceivingItems();

    } catch (error) {
        console.error('入庫確認エラー:', error);
        if (typeof showToast === 'function') {
            showToast(error.message || '入庫確認に失敗しました', 'error');
        }
    }
    } catch (error) {
        // 外側のtryブロックでのエラー処理
        console.error('入庫確認処理エラー:', error);
        if (typeof showToast === 'function') {
            showToast(error.message || '入庫確認処理に失敗しました', 'error');
        }
    } finally {
        // 必ずボタンの状態をリセット（成功・失敗・バリデーションエラー問わず）
        isSubmittingReceive = false;

        if (submitButton) {
            submitButton.disabled = false;
            submitButton.innerHTML = '入庫確定';
        }
    }
}

// ==== 手入力用入庫確認モーダル関数 ====

// 手入力用入庫確認モーダル表示
async function showManualReceiveModal() {
    try {
        // 比重プリセット一覧を読み込み
        await loadManualDensityPresets();

        // フォームを初期化
        document.getElementById('manualReceiveForm').reset();

        // 入荷日のデフォルトを本日に設定
        const receivedDateField = document.getElementById('manualReceivedDateInput');
        if (receivedDateField) {
            const now = new Date();
            const localDate = now.getFullYear() + '-' +
                String(now.getMonth() + 1).padStart(2, '0') + '-' +
                String(now.getDate()).padStart(2, '0');
            receivedDateField.value = localDate;
            
            // 購入月を自動設定
            updateManualPurchaseMonth();
        }

        // 長さのデフォルト値を設定
        const lengthInput = document.querySelector('input[name="length_mm"]');
        if (lengthInput && !lengthInput.value) {
            lengthInput.value = 2500;
        }

        // 初期ロット行を追加
        clearManualLotRows();
        addManualLotRow();

        // manualAddLotBtnのイベントリスナーを設定
        const addLotBtn = document.getElementById('manualAddLotBtn');
        if (addLotBtn) {
            addLotBtn.onclick = addManualLotRow;
        }

        // 計算用パラメータ変更時に合計を更新
        const diameterCalcInput = document.getElementById('manualDiameterCalcInput');
        const shapeCalcSelect = document.getElementById('manualShapeCalcSelect');
        const densityInput = document.getElementById('manualDensityInput');
        const lengthInput2 = document.querySelector('input[name="length_mm"]');

        if (diameterCalcInput) {
            diameterCalcInput.addEventListener('input', updateManualTotalQuantity);
        }
        if (shapeCalcSelect) {
            shapeCalcSelect.addEventListener('change', updateManualTotalQuantity);
        }
        if (densityInput) {
            densityInput.addEventListener('input', updateManualTotalQuantity);
        }
        if (lengthInput2) {
            lengthInput2.addEventListener('input', updateManualTotalQuantity);
        }

        // 入荷日変更時に購入月を自動設定
        setupManualPurchaseMonthAutoUpdate();

        // 単価入力時に金額を自動計算
        const unitPriceInput = document.getElementById('manualUnitPriceInput');
        if (unitPriceInput) {
            unitPriceInput.addEventListener('input', recalculateManualAmountFromWeight);
        }

        document.getElementById('manualReceiveModal').classList.remove('hidden');
        
        // 初期表示時に合計を更新
        updateManualTotalQuantity();
    } catch (error) {
        console.error('手入力用入庫確認モーダル表示エラー:', error);
        if (typeof showToast === 'function') {
            showToast('手入力用入庫確認画面の表示に失敗しました', 'error');
        }
    }
}

// 手入力用入庫確認モーダルを非表示
function hideManualReceiveModal() {
    document.getElementById('manualReceiveModal').classList.add('hidden');
    document.getElementById('manualReceiveForm').reset();

    // 比重プリセット選択をリセット
    const densityPresetSelect = document.getElementById('manualDensityPresetSelect');
    if (densityPresetSelect) {
        densityPresetSelect.value = '';
    }

    // ロット行をクリア
    clearManualLotRows();

    // 二重送信防止フラグをリセット
    isSubmittingManualReceive = false;

    // 送信ボタンの状態をリセット
    const submitButton = document.querySelector('#manualReceiveForm button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = false;
        submitButton.innerHTML = '入庫確定';
    }
}

// 手入力用購入月の自動設定
function setupManualPurchaseMonthAutoUpdate() {
    const receivedDateInput = document.getElementById('manualReceivedDateInput');
    const purchaseMonthInput = document.getElementById('manualPurchaseMonthInput');

    if (!receivedDateInput || !purchaseMonthInput) return;

    // 入荷日変更時に購入月を自動設定
    receivedDateInput.removeEventListener('change', updateManualPurchaseMonth);
    receivedDateInput.addEventListener('change', updateManualPurchaseMonth);

    // 初回設定（入荷日が既にある場合）
    if (receivedDateInput.value) {
        updateManualPurchaseMonth();
    }
}

function updateManualPurchaseMonth() {
    const receivedDateInput = document.getElementById('manualReceivedDateInput');
    const purchaseMonthInput = document.getElementById('manualPurchaseMonthInput');

    if (!receivedDateInput || !purchaseMonthInput || !receivedDateInput.value) return;

    const date = new Date(receivedDateInput.value);
    const year = date.getFullYear() % 100; // 下2桁
    const month = date.getMonth() + 1; // 1-12

    const yymm = String(year).padStart(2, '0') + String(month).padStart(2, '0');
    purchaseMonthInput.value = yymm;
}

// 手入力用比重プリセット一覧を読み込み
async function loadManualDensityPresets() {
    try {
        const response = await fetch('/api/density-presets/?is_active=true&limit=100');
        if (!response.ok) {
            console.warn('比重プリセットの取得に失敗しました');
            return;
        }

        const presets = await response.json();
        const selectElement = document.getElementById('manualDensityPresetSelect');

        if (!selectElement) return;

        // 既存のオプションをクリア（最初のプレースホルダーは残す）
        selectElement.innerHTML = '<option value="">プリセットから選択</option>';

        // プリセットを追加
        presets.forEach(preset => {
            const option = document.createElement('option');
            option.value = preset.density;
            option.textContent = `${preset.name} (${preset.density})`;
            option.dataset.name = preset.name;
            selectElement.appendChild(option);
        });

        // 選択イベントを設定
        selectElement.onchange = function () {
            const densityInput = document.getElementById('manualDensityInput');
            if (this.value && densityInput) {
                densityInput.value = this.value;

                // 選択したプリセット名をトーストで通知
                const selectedOption = this.options[this.selectedIndex];
                if (selectedOption && selectedOption.dataset.name && typeof showToast === 'function') {
                    showToast(`比重プリセット「${selectedOption.dataset.name}」を適用しました`, 'success');
                }

                // 合計を更新
                updateManualTotalQuantity();
            }
        };

    } catch (error) {
        console.error('比重プリセット読み込みエラー:', error);
    }
}

// 手入力用単価・金額の自動計算
function recalculateManualAmountFromWeight() {
    const unitPriceInput = document.getElementById('manualUnitPriceInput');
    const amountInput = document.getElementById('manualAmountInput');
    const totalWeightSpan = document.getElementById('manualTotalWeight');

    if (!unitPriceInput || !amountInput || !totalWeightSpan) return;

    const unitPrice = parseFloat(unitPriceInput.value) || 0;
    const totalWeight = parseFloat(totalWeightSpan.textContent) || 0;

    if (unitPrice > 0 && totalWeight > 0) {
        const amount = unitPrice * totalWeight;
        amountInput.value = amount.toFixed(2);
    } else {
        amountInput.value = '';
    }
}

// 手入力用ロット管理
let manualLotRowCounter = 0;

function addManualLotRow(quantity = null, weight = null, lotNumber = '', location = '', notes = '') {
    manualLotRowCounter++;
    const rowId = `manual-lot-row-${manualLotRowCounter}`;
    
    const row = document.createElement('div');
    row.id = rowId;
    row.className = 'border border-gray-200 rounded-lg p-4 bg-white';
    
    row.innerHTML = `
        <div class="flex justify-between items-center mb-3">
            <h4 class="text-sm font-medium text-gray-900">ロット ${manualLotRowCounter}</h4>
            <button type="button" onclick="removeManualLotRow('${rowId}')" 
                    class="text-red-500 hover:text-red-700 text-sm">
                <i class="fas fa-trash mr-1"></i>削除
            </button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">ロット番号 *</label>
                <input type="text" name="manual_lot_number_${manualLotRowCounter}" 
                       value="${lotNumber}" required
                       class="w-full p-2 border border-gray-300 rounded-md" 
                       placeholder="例: 2409-001">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">保管場所</label>
                <select name="manual_lot_location_${manualLotRowCounter}" 
                        class="w-full p-2 border border-gray-300 rounded-md">
                    <option value="">選択してください</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">本数</label>
                <input type="number" name="manual_lot_quantity_${manualLotRowCounter}" 
                       value="${quantity || ''}" step="1" min="0"
                       class="w-full p-2 border border-gray-300 rounded-md" 
                       placeholder="本数を入力">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">重量 (kg)</label>
                <input type="number" name="manual_lot_weight_${manualLotRowCounter}" 
                       value="${weight || ''}" step="0.001" min="0"
                       class="w-full p-2 border border-gray-300 rounded-md" 
                       placeholder="重量を入力">
            </div>
            <div class="md:col-span-2">
                <label class="block text-sm font-medium text-gray-700 mb-1">備考</label>
                <input type="text" name="manual_lot_notes_${manualLotRowCounter}" 
                       value="${notes}" 
                       class="w-full p-2 border border-gray-300 rounded-md" 
                       placeholder="備考があれば入力">
            </div>
        </div>
    `;
    
    document.getElementById('manualLotsContainer').appendChild(row);
    
    // 保管場所リストを読み込み
    loadManualLocations();
    
    // 入力変更時に合計を更新
    const quantityInput = row.querySelector(`input[name="manual_lot_quantity_${manualLotRowCounter}"]`);
    const weightInput = row.querySelector(`input[name="manual_lot_weight_${manualLotRowCounter}"]`);
    
    if (quantityInput) {
        quantityInput.addEventListener('input', updateManualTotalQuantity);
    }
    if (weightInput) {
        weightInput.addEventListener('input', updateManualTotalQuantity);
    }
}

function removeManualLotRow(rowId) {
    const row = document.getElementById(rowId);
    if (row) {
        row.remove();
        updateManualTotalQuantity();
    }
}

function clearManualLotRows() {
    document.getElementById('manualLotsContainer').innerHTML = '';
    manualLotRowCounter = 0;
}

// 手入力用保管場所リストを読み込み
async function loadManualLocations() {
    try {
        const response = await fetch('/api/locations/?is_active=true&limit=100');
        if (!response.ok) return;
        
        const locations = await response.json();
        const locationSelects = document.querySelectorAll('#manualLotsContainer select[name^="manual_lot_location_"]');
        
        locationSelects.forEach(select => {
            const currentValue = select.value;
            select.innerHTML = '<option value="">選択してください</option>';
            
            locations.forEach(location => {
                const option = document.createElement('option');
                option.value = location.id;
                option.textContent = location.name;
                select.appendChild(option);
            });
            
            if (currentValue) {
                select.value = currentValue;
            }
        });
    } catch (error) {
        console.error('保管場所読み込みエラー:', error);
    }
}

// 手入力用合計数量・重量の更新
function updateManualTotalQuantity() {
    const rows = document.querySelectorAll('#manualLotsContainer > div');
    let totalQuantity = 0;
    let totalWeight = 0;
    
    rows.forEach(row => {
        const quantityInput = row.querySelector('input[name^="manual_lot_quantity_"]');
        const weightInput = row.querySelector('input[name^="manual_lot_weight_"]');
        
        const quantity = parseInt(quantityInput?.value) || 0;
        const weight = parseFloat(weightInput?.value) || 0;
        
        totalQuantity += quantity;
        totalWeight += weight;
    });
    
    // 手入力の場合は参考値を表示しない
    document.getElementById('manualTotalQuantity').textContent = totalQuantity;
    document.getElementById('manualTotalWeight').textContent = totalWeight.toFixed(3);
    document.getElementById('manualOrderedQuantity').textContent = '-';
    document.getElementById('manualTotalQuantityRef').textContent = '-';
    document.getElementById('manualTotalWeightRef').textContent = '-';
    
    // 単価・金額の再計算
    recalculateManualAmountFromWeight();
}

// 手入力用送信中フラグ
let isSubmittingManualReceive = false;

// 手入力用入庫確認処理
async function handleManualReceive(event) {
    event.preventDefault();

    // 二重送信防止
    if (isSubmittingManualReceive) {
        console.log('手入力入庫確認処理中のため、重複送信を防止しました');
        return;
    }

    // 送信ボタンを取得して無効化
    const submitButton = event.target.querySelector('button[type="submit"]');
    if (submitButton) {
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>処理中...';
    }

    // 送信中フラグを設定
    isSubmittingManualReceive = true;

    try {
        const formData = new FormData(event.target);

        // 手入力発注情報を取得
        const orderData = {
            order_number: formData.get('order_number'),
            supplier: formData.get('supplier'),
            order_date: formData.get('order_date'),
            expected_delivery_date: formData.get('delivery_date'),
            item_name: formData.get('material_spec'),
            order_quantity: parseInt(formData.get('order_quantity')) || null,
            ordered_weight_kg: parseFloat(formData.get('order_weight')) || null,
            set_scheduled_date: formData.get('schedule_date') || null,
            machine_no: formData.get('machine_number') || null
        };

        // バリデーション
        if (!orderData.order_number || !orderData.supplier || !orderData.order_date || 
            !orderData.expected_delivery_date || !orderData.item_name) {
            if (typeof showToast === 'function') {
                showToast('必須項目をすべて入力してください', 'error');
            }
            return;
        }

        if (!orderData.order_quantity && !orderData.ordered_weight_kg) {
            if (typeof showToast === 'function') {
                showToast('発注数量または重量のいずれかを入力してください', 'error');
            }
            return;
        }

        // 計算用パラメータを取得
        const diameter_mm = parseFloat(formData.get('diameter_mm'));
        const shape = formData.get('shape');
        const density = parseFloat(formData.get('density'));
        const length_mm = parseInt(formData.get('length_mm'));

        // バリデーション
        if (isNaN(diameter_mm) || diameter_mm <= 0) {
            if (typeof showToast === 'function') {
                showToast('径を正しく入力してください', 'error');
            }
            return;
        }

        if (!shape || !['round', 'hexagon', 'square'].includes(shape)) {
            if (typeof showToast === 'function') {
                showToast('形状を選択してください', 'error');
            }
            return;
        }

        if (isNaN(density) || density <= 0) {
            if (typeof showToast === 'function') {
                showToast('比重を正しく入力してください', 'error');
            }
            return;
        }

        if (isNaN(length_mm) || length_mm <= 0) {
            if (typeof showToast === 'function') {
                showToast('長さを正しく入力してください', 'error');
            }
            return;
        }

        // 購入月を取得
        const purchaseMonth = formData.get('purchase_month');
        if (!purchaseMonth || !/^\d{4}$/.test(purchaseMonth)) {
            if (typeof showToast === 'function') {
                showToast('購入月をYYMM形式（例: 2501）で入力してください', 'error');
            }
            return;
        }

        // 単価・金額を取得
        const unitPrice = formData.get('unit_price');
        const amount = formData.get('amount');

        // まず発注を作成
        const createOrderResponse = await fetch('/api/purchase-orders/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData)
        });

        if (!createOrderResponse.ok) {
            const errorText = await createOrderResponse.text();
            let errorMsg = errorText;
            try {
                const parsed = JSON.parse(errorText);
                errorMsg = parsed.detail || errorMsg;
            } catch (e) {
                errorMsg = errorMsg?.substring(0, 200) || `ステータス ${createOrderResponse.status}`;
            }
            throw new Error(`発注作成に失敗しました: ${errorMsg}`);
        }

        const createdOrder = await createOrderResponse.json();
        const orderId = createdOrder.id;

        // 次に発注アイテムを作成
        const itemData = {
            purchase_order_id: orderId,
            item_name: orderData.item_name,
            order_type: orderData.ordered_weight_kg ? 'weight' : 'quantity',
            ordered_quantity: orderData.order_quantity,
            ordered_weight_kg: orderData.ordered_weight_kg,
            set_scheduled_date: orderData.set_scheduled_date,
            machine_no: orderData.machine_no
        };

        const createItemResponse = await fetch('/api/purchase-orders/items/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(itemData)
        });

        if (!createItemResponse.ok) {
            const errorText = await createItemResponse.text();
            let errorMsg = errorText;
            try {
                const parsed = JSON.parse(errorText);
                errorMsg = parsed.detail || errorMsg;
            } catch (e) {
                errorMsg = errorMsg?.substring(0, 200) || `ステータス ${createItemResponse.status}`;
            }
            throw new Error(`発注アイテム作成に失敗しました: ${errorMsg}`);
        }

        const createdItem = await createItemResponse.json();
        const itemId = createdItem.id;

        // 共通入庫データ
        const commonMaterialData = {
            diameter_mm: diameter_mm,
            shape: shape,
            density: density,
            length_mm: length_mm,
            received_date: formData.get('received_date') + 'T00:00:00',
            purchase_month: purchaseMonth
        };

        // 単価・金額を追加（値が入力されている場合のみ）
        if (unitPrice && unitPrice.trim() !== '' && !isNaN(parseFloat(unitPrice))) {
            commonMaterialData.unit_price = parseFloat(unitPrice);
        }
        if (amount && amount.trim() !== '' && !isNaN(parseFloat(amount))) {
            commonMaterialData.amount = parseFloat(amount);
        }

        // 各ロット情報を収集
        const lots = [];
        for (let i = 1; i <= manualLotRowCounter; i++) {
            const lotRow = document.getElementById(`manual-lot-row-${i}`);
            if (!lotRow) continue;

            const lotNumberInput = lotRow.querySelector(`input[name="manual_lot_number_${i}"]`);
            const quantityInput = lotRow.querySelector(`input[name="manual_lot_quantity_${i}"]`);
            const weightInput = lotRow.querySelector(`input[name="manual_lot_weight_${i}"]`);
            const locationElement = lotRow.querySelector(`select[name="manual_lot_location_${i}"]`);
            const notesInput = lotRow.querySelector(`input[name="manual_lot_notes_${i}"]`);

            const lotNumber = lotNumberInput?.value || '';
            const quantityStr = quantityInput?.value || '';
            const weightStr = weightInput?.value || '';
            const location = locationElement?.value || '';
            const lotNotes = notesInput?.value || '';

            if (!lotNumber || lotNumber.trim() === '') {
                if (typeof showToast === 'function') {
                    showToast(`ロット ${i}: ロット番号は必須です`, 'error');
                }
                return;
            }

            const quantity = quantityStr && quantityStr.trim() !== '' ? parseInt(quantityStr, 10) : null;
            const weight = weightStr && weightStr.trim() !== '' ? parseFloat(weightStr) : null;

            if (!quantity && !weight) {
                if (typeof showToast === 'function') {
                    showToast(`ロット ${i}: 本数または重量のいずれかを入力してください`, 'error');
                }
                return;
            }

            const lotData = {
                lot_number: lotNumber.trim(),
                location_id: location && location.trim() !== '' ? parseInt(location) : null,
                purchase_month: purchaseMonth,
                notes: lotNotes.trim() || null
            };

            if (quantity) {
                lotData.received_quantity = quantity;
            }
            if (weight) {
                lotData.received_weight_kg = weight;
            }

            lots.push(lotData);
        }

        if (lots.length === 0) {
            if (typeof showToast === 'function') {
                showToast('少なくとも1つのロットを入力してください', 'error');
            }
            return;
        }

        // 各ロットに対して入庫処理を実行
        let appliedCount = 0;
        for (const lot of lots) {
            const receiveData = {
                ...commonMaterialData,
                lot_number: lot.lot_number,
                notes: lot.notes
            };

            if (typeof lot.received_quantity === 'number') {
                receiveData.received_quantity = lot.received_quantity;
            }
            if (typeof lot.received_weight_kg === 'number') {
                receiveData.received_weight_kg = lot.received_weight_kg;
            }

            if (lot.location_id) {
                receiveData.location_id = lot.location_id;
            }

            const response = await fetch(`/api/purchase-orders/items/${itemId}/receive/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(receiveData)
            });

            if (!response.ok) {
                let errorMsg;
                const responseText = await response.text();
                console.error('サーバーエラー（テキスト）:', responseText);

                try {
                    const error = JSON.parse(responseText);
                    errorMsg = error.detail || JSON.stringify(error);
                } catch (e) {
                    errorMsg = responseText.substring(0, 200) || `サーバーエラー (${response.status})`;
                }
                throw new Error(`ロット ${lot.lot_number}: ${errorMsg}`);
            }

            appliedCount++;
        }

        if (typeof showToast === 'function') {
            showToast(`${appliedCount}件のロットを登録しました（発注番号: ${orderData.order_number}）`, 'success');
        }
        
        hideManualReceiveModal();
        loadReceivingItems();

    } catch (error) {
        console.error('手入力入庫確認エラー:', error);
        if (typeof showToast === 'function') {
            showToast(error.message || '手入力入庫確認に失敗しました', 'error');
        }
    } finally {
        // 必ずボタンの状態をリセット
        isSubmittingManualReceive = false;

        if (submitButton) {
            submitButton.disabled = false;
            submitButton.innerHTML = '入庫確定';
        }
    }
}

// 径入力パース関数（receiving.jsから移植）
const SHAPE_SYMBOL_MAP = {
    round: ['φ', 'Φ', '⌀', 'Ø', 'ø', 'ϕ', '￠'],
    hexagon: ['H', 'h', 'Ｈ', 'ｈ'],
    square: ['□', '■', '口', '▢']
};

function parseDiameterInputValue(raw) {
    if (!raw || !raw.trim()) {
        // 空欄は許容（形状・径は未設定として送信）
        return { shape: null, diameter_mm: null };
    }
    let text = raw.normalize('NFKC').trim();
    let shape = null;

    const firstChar = text.charAt(0);
    for (const [key, symbols] of Object.entries(SHAPE_SYMBOL_MAP)) {
        if (symbols.includes(firstChar)) {
            shape = key;
            text = text.slice(1).trimStart();
            break;
        }
    }

    if (!shape) {
        return { error: '先頭に形状記号（φ・H・□など）を付けてください' };
    }

    text = text.replace(/(mm|㎜)/gi, ' ');
    const numberMatch = text.match(/(\d+(?:[.,]\d+)?)/);
    if (!numberMatch) {
        return { error: '径の数値が確認できません' };
    }

    const diameter = parseFloat(numberMatch[1].replace(',', '.'));
    if (!(diameter > 0)) {
        return { error: '径は正の数で入力してください' };
    }

    return { shape, diameter_mm: diameter };
}

// 形状・径を入力フィールド用に整形
function formatDiameterInputValueForDisplay(shape, diameterMm) {
    if (!shape || typeof diameterMm !== 'number') return '';
    const d = Number(diameterMm);
    const s = String(shape).toLowerCase();
    if (s === 'round') return `φ${d}`;
    if (s === 'hexagon') return `H${d}`;
    if (s === 'square') return `□${d}`;
    return `${d}`;
}

// ==== 検品タブ ====
let currentInspectionLotId = null;
let inspectionAllItems = [];
let currentInspectionPage = 1;
const inspectionPageSize = 25;

function initializeInspectionTab() {
    document.getElementById('loadInspectionTargetBtn')?.addEventListener('click', loadInspectionTargetByCode);
    document.getElementById('resetInspectionFormBtn')?.addEventListener('click', resetInspectionForm);
    document.getElementById('inspectionForm')?.addEventListener('submit', submitInspection);
    document.getElementById('refreshInspectionListBtn')?.addEventListener('click', () => loadInspectionItemsList(1));

    // 検品済み一覧（検索）のイベント設定
    document.getElementById('resetInspectedLotsFiltersBtn')?.addEventListener('click', resetInspectedLotsFilters);
    // 入力時点でのリアルタイム検索（debounce）
    const debouncedLoadInspected = debounce(() => loadInspectedLotsList(1), 300);
    ['inspectedMaterialFilter','inspectedLotFilter','inspectedOrderNumberFilter'].forEach((id)=>{
        const el = document.getElementById(id);
        el?.addEventListener('input', debouncedLoadInspected);
        el?.addEventListener('keyup', (e)=>{ if (e.key === 'Enter') loadInspectedLotsList(1); });
        el?.addEventListener('change', () => loadInspectedLotsList(1));
    });

    // 入庫済みアイテムから選択のリアルタイム検索
    const debouncedRenderInspection = debounce(() => renderInspectionItemsList(1), 300);
    ['inspectionMaterialFilter','inspectionLotFilter','inspectionOrderNumberFilter'].forEach((id)=>{
        const el = document.getElementById(id);
        el?.addEventListener('input', debouncedRenderInspection);
        el?.addEventListener('change', () => renderInspectionItemsList(1));
    });
    document.getElementById('resetInspectionSelectionFiltersBtn')?.addEventListener('click', resetInspectionSelectionFilters);

    // 検品済み一覧トグル
    document.getElementById('toggleInspectedSectionBtn')?.addEventListener('click', toggleInspectedSection);

    // 初期は非表示（ロードしない）

    // デフォルト日時を現在に設定
    const now = new Date();
    const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
        .toISOString().slice(0, 16);
    const dtEl = document.getElementById('inspectedAtInput');
    if (dtEl) dtEl.value = local;
}

// 入庫済みアイテム一覧を読み込み
async function loadInspectionItemsList(page = 1) {
    const tableBody = document.getElementById('inspectionItemsListBody');
    const loading = document.getElementById('inspectionListLoading');
    const empty = document.getElementById('inspectionListEmpty');

    loading.classList.remove('hidden');
    tableBody.innerHTML = '';
    empty.classList.add('hidden');

    try {
        // 検品待ちのロットを取得
        const response = await fetch('/api/inspections/lots/pending/');
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const lots = await response.json();

        console.log('取得したロット数:', lots.length); // デバッグ用
        console.log('最初のロットのデータ構造:', lots[0]); // デバッグ用

        loading.classList.add('hidden');

        if (!Array.isArray(lots) || lots.length === 0) {
            empty.classList.remove('hidden');
            inspectionAllItems = [];
            return;
        }

        // ロットデータを検品アイテム形式に変換
        const convertedItems = lots.map(lot => ({
            id: lot.id,
            management_code: lot.lot_number,
            material: lot.material,
            lot: {
                id: lot.id,
                lot_number: lot.lot_number,
                inspection_status: lot.inspection_status,
                initial_weight_kg: lot.initial_weight_kg,
                notes: lot.notes,
                order_number: lot.purchase_order?.order_number
            },
            total_weight_kg: lot.initial_weight_kg,
            current_quantity: lot.initial_quantity
        }));

        console.log('変換後アイテム数:', convertedItems.length); // デバッグ用

        // 全アイテムを保存
        inspectionAllItems = convertedItems;

        // フィルタを適用してレンダリング（クライアントサイド）
        renderInspectionItemsList(page);

    } catch (error) {
        loading.classList.add('hidden');
        console.error('検品待ちロット読み込みエラー:', error);
        if (typeof showToast === 'function') {
            showToast('検品待ちロットの読み込みに失敗しました: ' + error.message, 'error');
        }
    }
}

// 入庫済みアイテム一覧（クライアントサイドフィルタ適用後のレンダリング）
function renderInspectionItemsList(page = 1) {
    const tableBody = document.getElementById('inspectionItemsListBody');
    const empty = document.getElementById('inspectionListEmpty');

    if (!tableBody || !empty) return;

    tableBody.innerHTML = '';
    empty.classList.add('hidden');

    // テキストフィルタ取得
    const materialSpec = (document.getElementById('inspectionMaterialFilter')?.value || '').trim().toLowerCase();
    const lotNumber = (document.getElementById('inspectionLotFilter')?.value || '').trim().toLowerCase();
    const orderNumber = (document.getElementById('inspectionOrderNumberFilter')?.value || '').trim().toLowerCase();

    // フィルタ適用
    let filtered = inspectionAllItems;
    if (materialSpec) {
        filtered = filtered.filter(item => (item.material?.display_name || item.material?.name || '').toLowerCase().includes(materialSpec));
    }
    if (lotNumber) {
        filtered = filtered.filter(item => (item.lot?.lot_number || '').toLowerCase().includes(lotNumber));
    }
    if (orderNumber) {
        filtered = filtered.filter(item => (item.lot?.order_number || '').toLowerCase().includes(orderNumber));
    }

    if (!filtered || filtered.length === 0) {
        empty.classList.remove('hidden');
        renderPagination('inspection', 1, 1, renderInspectionItemsList);
        return;
    }

    // ページネーション処理
    const totalPages = Math.ceil(filtered.length / inspectionPageSize);
    currentInspectionPage = Math.min(page, totalPages);
    const startIndex = (currentInspectionPage - 1) * inspectionPageSize;
    const endIndex = startIndex + inspectionPageSize;
    const pageItems = filtered.slice(startIndex, endIndex);

    pageItems.forEach(item => {
        const row = createInspectionItemRow(item);
        tableBody.appendChild(row);
    });

    // ページネーション表示（クライアントサイドのレンダラを渡す）
    renderPagination('inspection', currentInspectionPage, totalPages, renderInspectionItemsList);
}

function resetInspectionSelectionFilters() {
    ['inspectionMaterialFilter','inspectionLotFilter','inspectionOrderNumberFilter'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    renderInspectionItemsList(1);
}

// 検品済み一覧のフィルタをリセット
function resetInspectedLotsFilters() {
    ['inspectedOrderNumberFilter','inspectedMaterialFilter','inspectedLotFilter'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    loadInspectedLotsList(1);
}

function createInspectionItemRow(item) {
    const row = document.createElement('tr');
    row.className = 'hover:bg-gray-50';

    // 材料仕様はExcelから取得したフルネーム（display_name）を表示
    const materialSpec = item.material?.display_name || item.material?.name || '-';

    const lotNumber = item.lot?.lot_number || '-';
    const managementCode = item.management_code || '';
    const lotNotes = item.lot?.notes || '-';

    // 重量（初期登録値を優先表示）
    const initialWeight = item.lot?.initial_weight_kg ?? 0;
    const totalWeight = initialWeight > 0 ? initialWeight : (item.total_weight_kg || 0);
    const weightDisplay = totalWeight > 0 ? `${Number(totalWeight).toFixed(3)}kg` : '-';

    // 検品状態バッジ
    const inspectionStatus = (item.lot?.inspection_status || 'pending').toLowerCase();

    console.log(`アイテム ${managementCode} の検品ステータス:`, inspectionStatus); // デバッグ

    let statusText = '未検品';
    let statusClass = 'bg-amber-100 text-amber-700';

    if (inspectionStatus === 'passed') {
        statusText = '合格';
        statusClass = 'bg-green-100 text-green-700';
    } else if (inspectionStatus === 'failed') {
        statusText = '不合格';
        statusClass = 'bg-red-100 text-red-700';
    }

    // ロット番号がない場合はボタンを無効化
    const buttonDisabled = !lotNumber;
    const buttonClass = buttonDisabled
        ? 'bg-gray-400 text-white px-2 py-1 rounded text-xs cursor-not-allowed'
        : 'bg-indigo-600 text-white px-2 py-1 rounded text-xs hover:bg-indigo-700';

    const buttonOnClick = buttonDisabled ? '' : `onclick="selectInspectionItem('${lotNumber}')"`;

    row.innerHTML = `
        <td class="px-3 py-2 text-xs text-gray-900">${materialSpec}</td>
        <td class="px-3 py-2 text-xs text-gray-600">${lotNumber}</td>
        <td class="px-3 py-2 text-xs text-gray-600">${item.current_quantity}本</td>
        <td class="px-3 py-2 text-xs text-gray-600">${weightDisplay}</td>
        <td class="px-3 py-2 text-xs text-gray-600">${lotNotes}</td>
        <td class="px-3 py-2">
            <span class="px-2 py-1 rounded-full text-xs font-medium ${statusClass}">${statusText}</span>
        </td>
        <td class="px-3 py-2">
            <button ${buttonOnClick} ${buttonDisabled ? 'disabled' : ''}
                    class="${buttonClass}">
                ${buttonDisabled ? 'ロット番号なし' : '選択'}
            </button>
        </td>
    `;

    return row;
}

function selectInspectionItem(lotNumber) {
    // ロット番号入力欄に設定
    const codeInput = document.getElementById('inspectionCodeInput');
    if (codeInput) {
        codeInput.value = lotNumber;
    }

    // 自動で検品対象を読み込み
    loadInspectionTargetByCode();

    // 検品フォームまでスクロール
    const inspectionForm = document.getElementById('inspectionForm');
    if (inspectionForm) {
        inspectionForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

async function loadInspectionTargetByCode() {
    const codeInput = document.getElementById('inspectionCodeInput');
    const infoEl = document.getElementById('inspectionTargetInfo');
    const lotNumber = (codeInput?.value || '').trim();

    console.log('検品対象読み込み開始:', lotNumber); // デバッグ

    if (!lotNumber) {
        if (typeof showToast === 'function') {
            showToast('ロット番号を入力してください', 'error');
        }
        return;
    }

    try {
        const res = await fetch(`/api/inspections/lots/search/${encodeURIComponent(lotNumber)}`);
        console.log('API応答ステータス:', res.status); // デバッグ

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'ロット番号の読み込みに失敗しました');
        }
        const item = await res.json();
        console.log('取得したアイテム:', item); // デバッグ

        currentInspectionLotId = item?.lot?.id || null;
        console.log('設定したLot ID:', currentInspectionLotId); // デバッグ

        if (!currentInspectionLotId) {
            if (typeof showToast === 'function') {
                showToast('該当ロットが見つかりません', 'error');
            }
            return;
        }

        if (infoEl) {
            const lotNum = item?.lot?.lot_number || '-';
            const qty = item?.current_quantity ?? '-';
            const materialName = item?.material?.display_name || item?.material?.name || '-';
            const length = item?.lot?.length_mm || '-';
            const initialWeight = item?.lot?.initial_weight_kg ?? null;
            const totalWeightCandidate = (initialWeight != null && initialWeight > 0) ? initialWeight : (item?.total_weight_kg ?? null);
            const weight = (totalWeightCandidate != null && totalWeightCandidate > 0) ? `${Number(totalWeightCandidate).toFixed(3)}kg` : '-';
            const lotNotes = item?.lot?.notes || '';

            console.log('ロット備考データ:', lotNotes); // デバッグ用

            // 検品ステータスを取得
            const inspectionStatus = (item?.lot?.inspection_status || 'pending').toLowerCase();
            let statusBadge = '';
            if (inspectionStatus === 'passed') {
                statusBadge = '<span class="px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">合格</span>';
            } else if (inspectionStatus === 'failed') {
                statusBadge = '<span class="px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">不合格</span>';
            } else {
                statusBadge = '<span class="px-2 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-700">未検品</span>';
            }

            infoEl.innerHTML = `
                <div class="bg-blue-50 border-2 border-blue-200 rounded-lg p-4">
                    <div class="grid grid-cols-2 gap-3 text-sm">
                        <div>
                            <span class="text-blue-600 font-medium">材料:</span>
                            <span class="text-gray-900 ml-2">${materialName}</span>
                        </div>
                        <div>
                            <span class="text-blue-600 font-medium">ロット番号:</span>
                            <span class="text-gray-900 ml-2 font-mono">${lotNum}</span>
                        </div>
                        <div>
                            <span class="text-blue-600 font-medium">現在検品状態:</span>
                            <span class="ml-2">${statusBadge}</span>
                        </div>
                        <div>
                            <span class="text-blue-600 font-medium">本数:</span>
                            <span class="text-gray-900 ml-2">${qty}本</span>
                        </div>
                        <div>
                            <span class="text-blue-600 font-medium">重量:</span>
                            <span class="text-gray-900 ml-2">${weight}</span>
                        </div>
                        <div>
                            <span class="text-blue-600 font-medium">長さ:</span>
                            <span class="text-gray-900 ml-2">${length}mm</span>
                        </div>
                        ${lotNotes ? `
                        <div class="col-span-2">
                            <span class="text-blue-600 font-medium">ロット備考:</span>
                            <span class="text-gray-900 ml-2">${lotNotes}</span>
                        </div>
                        ` : ''}
                    </div>
                </div>
            `;
            infoEl.classList.remove('text-gray-600');
            infoEl.classList.add('text-blue-700');
        }

        if (typeof showToast === 'function') {
            showToast('検品対象を読み込みました', 'success');
        }

        // 保存済みの検品詳細があればフォームへ反映
        if (currentInspectionLotId) {
            await populateInspectionFormFromSaved(currentInspectionLotId);
        }
    } catch (e) {
        console.error('ロット番号読み込みエラー:', e);
        if (typeof showToast === 'function') {
            showToast(e.message || 'ロット番号の読み込みに失敗しました', 'error');
        }
        if (infoEl) {
            infoEl.innerHTML = '<p class="text-gray-600">ロット番号を入力して読み込んでください。</p>';
            infoEl.classList.remove('text-blue-700');
            infoEl.classList.add('text-gray-600');
        }
    }
}

function resetInspectionForm() {
    document.getElementById('inspectionForm').reset();
    currentInspectionLotId = null;
    const infoEl = document.getElementById('inspectionTargetInfo');
    if (infoEl) {
        infoEl.innerHTML = '<p class="text-gray-600">ロット番号を入力して読み込んでください。</p>';
        infoEl.classList.remove('text-blue-700');
        infoEl.classList.add('text-gray-600');
    }

    // デフォルト日時を現在に設定
    const now = new Date();
    const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
        .toISOString().slice(0, 16);
    const dtEl = document.getElementById('inspectedAtInput');
    if (dtEl) dtEl.value = local;
}

async function populateInspectionFormFromSaved(lotId) {
    try {
        const res = await fetch(`/api/inventory/lots/${lotId}/inspection/`);
        if (!res.ok) {
            console.warn('検品詳細の取得に失敗:', res.status);
            return;
        }
        const detail = await res.json();

        // 日時（ローカル）
        if (detail.inspected_at) {
            const dt = new Date(detail.inspected_at);
            const local = new Date(dt.getTime() - dt.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
            const dtEl = document.getElementById('inspectedAtInput');
            if (dtEl) dtEl.value = local;
        }

        // セレクト・テキスト
        const setSelectBool = (id, val) => {
            const el = document.getElementById(id);
            if (!el) return;
            if (val === null || typeof val === 'undefined') {
                el.value = '';
            } else {
                el.value = val ? 'true' : 'false';
            }
        };

        setSelectBool('bendingOkSelect', detail.bending_ok);
        setSelectBool('scratchOkSelect', detail.scratch_ok);
        setSelectBool('dirtOkSelect', detail.dirt_ok);

        const judgementEl = document.getElementById('inspectionJudgementSelect');
        if (judgementEl) judgementEl.value = detail.inspection_judgement || '';

        const byEl = document.getElementById('inspectedByInput');
        if (byEl) byEl.value = detail.inspected_by_name || '';

        const notesEl = document.getElementById('inspectionNotesInput');
        if (notesEl) notesEl.value = detail.inspection_notes || '';

        // 寸法入力
        const numMap = [
            ['dim1LeftMax', 'dim1_left_max'],
            ['dim1LeftMin', 'dim1_left_min'],
            ['dim1CenterMax', 'dim1_center_max'],
            ['dim1CenterMin', 'dim1_center_min'],
            ['dim1RightMax', 'dim1_right_max'],
            ['dim1RightMin', 'dim1_right_min'],
            ['dim2LeftMax', 'dim2_left_max'],
            ['dim2LeftMin', 'dim2_left_min'],
            ['dim2CenterMax', 'dim2_center_max'],
            ['dim2CenterMin', 'dim2_center_min'],
            ['dim2RightMax', 'dim2_right_max'],
            ['dim2RightMin', 'dim2_right_min']
        ];

        numMap.forEach(([id, key]) => {
            const el = document.getElementById(id);
            if (!el) return;
            const val = detail[key];
            el.value = (val === null || typeof val === 'undefined') ? '' : String(val);
        });

        if (typeof showToast === 'function') {
            showToast('保存済み検品データをフォームに反映しました', 'success');
        }
    } catch (e) {
        console.error('検品詳細取得エラー:', e);
    }
}

async function submitInspection(event) {
    event.preventDefault();

    console.log('検品送信開始 - currentInspectionLotId:', currentInspectionLotId); // デバッグ

    if (!currentInspectionLotId) {
        if (typeof showToast === 'function') {
            showToast('検品対象の管理コードを読み込んでください', 'error');
        }
        return;
    }

    const inspectedAtStr = document.getElementById('inspectedAtInput').value;
    // 実測値は廃止
    // 外観は廃止。曲がりはセレクトに統一
    const bendingOk = document.getElementById('bendingOkSelect') ? (document.getElementById('bendingOkSelect').value === 'true') : true;
    const inspectedBy = document.getElementById('inspectedByInput').value.trim();
    const notes = document.getElementById('inspectionNotesInput').value.trim();

    // 追加項目
    const judgementVal = document.getElementById('inspectionJudgementSelect') ? document.getElementById('inspectionJudgementSelect').value : '';
    const scratchOk = document.getElementById('scratchOkSelect') ? (document.getElementById('scratchOkSelect').value === 'true') : true;
    const dirtOk = document.getElementById('dirtOkSelect') ? (document.getElementById('dirtOkSelect').value === 'true') : true;

    const getNum = (id) => {
        const el = document.getElementById(id);
        if (!el || el.value === '') return null;
        const n = parseFloat(el.value);
        return isNaN(n) ? null : n;
    };
    const dim1LeftMax = getNum('dim1LeftMax');
    const dim1LeftMin = getNum('dim1LeftMin');
    const dim1CenterMax = getNum('dim1CenterMax');
    const dim1CenterMin = getNum('dim1CenterMin');
    const dim1RightMax = getNum('dim1RightMax');
    const dim1RightMin = getNum('dim1RightMin');
    const dim2LeftMax = getNum('dim2LeftMax');
    const dim2LeftMin = getNum('dim2LeftMin');
    const dim2CenterMax = getNum('dim2CenterMax');
    const dim2CenterMin = getNum('dim2CenterMin');
    const dim2RightMax = getNum('dim2RightMax');
    const dim2RightMin = getNum('dim2RightMin');

    // 判定優先度: 手動選択があればそれを優先、なければ自動（AND）
    let inspectionStatus = 'failed';
    if (judgementVal === 'pass') {
        inspectionStatus = 'passed';
    } else if (judgementVal === 'fail') {
        inspectionStatus = 'failed';
    } else {
        inspectionStatus = (bendingOk && scratchOk && dirtOk) ? 'passed' : 'failed';
    }

    const payload = {
        inspection_date: inspectedAtStr ? new Date(inspectedAtStr) : new Date(),
        bending_ok: bendingOk,
        inspector_name: inspectedBy || '',
        notes: notes || '',
        scratch_ok: scratchOk,
        dirt_ok: dirtOk,
        inspection_judgement: judgementVal || null
    };

    console.log('検品データペイロード:', payload); // デバッグ

    try {
        const url = `/api/inspections/lots/${currentInspectionLotId}/`;
        console.log('検品API URL:', url); // デバッグ

        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        console.log('検品API応答ステータス:', res.status); // デバッグ

        if (res.ok) {
            const result = await res.json();
            console.log('検品登録成功:', result); // デバッグ
            console.log('検品ステータス:', result.inspection_status); // デバッグ

            if (typeof showToast === 'function') {
                const statusText = result.inspection_status === 'passed' ? '合格' : result.inspection_status === 'failed' ? '不合格' : '完了';
                showToast(`検品結果を登録しました（${statusText}）`, 'success');
            }
            resetInspectionForm();

            // データベースの更新を待ってから一覧を再読み込み
            setTimeout(() => {
                console.log('検品一覧を再読み込み中...'); // デバッグ
                loadInspectionItemsList();
                loadReceivingItems();
            }, 500);
        } else {
            const err = await res.json().catch(() => ({}));
            console.error('検品登録失敗:', err); // デバッグ
            if (typeof showToast === 'function') {
                showToast(err.detail || '検品登録に失敗しました', 'error');
            }
        }
    } catch (e) {
        console.error('検品登録エラー:', e);
        if (typeof showToast === 'function') {
            showToast('検品登録に失敗しました: ' + e.message, 'error');
        }
    }
}

// ==== 印刷タブ ====
let currentPrintItemCode = null;
let currentPrintLotId = null;

let printAllItems = [];
let currentPrintPage = 1;
const printPageSize = 25;

function initializePrintTab() {
    document.getElementById('refreshPrintBtn')?.addEventListener('click', () => loadPrintableItems(1));
    document.getElementById('resetPrintFiltersBtn')?.addEventListener('click', resetPrintFilters);

    // リアルタイム検索（入力時にdebounceで検索実行）
    document.getElementById('printMaterialFilter')?.addEventListener('input', debounce(() => searchPrintItems(), 300));
    document.getElementById('printLotFilter')?.addEventListener('input', debounce(() => searchPrintItems(), 300));

    // 印刷モーダル
    document.getElementById('closePrintModal')?.addEventListener('click', hidePrintModal);
    document.getElementById('cancelPrint')?.addEventListener('click', hidePrintModal);
    document.getElementById('executePrintLotNumber')?.addEventListener('click', executePrintLotNumber);

    // ESCキーでモーダルを閉じる
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            const printModal = document.getElementById('printModal');
            if (printModal && !printModal.classList.contains('hidden')) {
                hidePrintModal();
            }
        }
    });
}

async function loadPrintableItems(page = 1) {
    const tableBody = document.getElementById('printItemsTableBody');
    const loading = document.getElementById('printLoading');
    const empty = document.getElementById('printEmpty');

    loading.classList.remove('hidden');
    tableBody.innerHTML = '';
    empty.classList.add('hidden');

    try {
        // 検品完了（PASSED）のアイテムを取得
        const response = await fetch('/api/inventory/?skip=0&limit=1000&is_active=true&has_stock=true');
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const items = await response.json();

        loading.classList.add('hidden');

        // 検品完了（PASSED）のアイテムをフィルタ
        const printableItems = Array.isArray(items)
            ? items.filter(item => {
                const status = item.lot?.inspection_status;
                return status && status.toLowerCase() === 'passed';
            })
            : [];

        if (printableItems.length === 0) {
            empty.classList.remove('hidden');
            printAllItems = [];
            return;
        }

        // 全アイテムを保存
        printAllItems = printableItems;

        // ページネーション処理
        const totalPages = Math.ceil(printAllItems.length / printPageSize);
        currentPrintPage = Math.min(page, totalPages);
        const startIndex = (currentPrintPage - 1) * printPageSize;
        const endIndex = startIndex + printPageSize;
        const pageItems = printAllItems.slice(startIndex, endIndex);

        pageItems.forEach(item => {
            const row = createPrintItemRow(item);
            tableBody.appendChild(row);
        });

        // ページネーション表示
        renderPagination('print', currentPrintPage, totalPages, loadPrintableItems);

    } catch (error) {
        loading.classList.add('hidden');
        console.error('印刷可能アイテム読み込みエラー:', error);
        if (typeof showToast === 'function') {
            showToast('印刷可能アイテムの読み込みに失敗しました: ' + error.message, 'error');
        }
    }
}

function createPrintItemRow(item) {
    const row = document.createElement('tr');
    row.className = 'hover:bg-gray-50';

    const materialName = item.material?.display_name || item.material?.name || '-';
    const lotNumber = item.lot?.lot_number || '-';
    const inspectionDate = item.lot?.inspected_at
        ? new Date(item.lot.inspected_at).toLocaleDateString('ja-JP')
        : '-';

    row.innerHTML = `
        <td class="px-4 py-3 text-sm font-mono text-gray-900">${lotNumber}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${materialName}</td>
        <td class="px-4 py-3 text-sm text-gray-600">${item.current_quantity}本</td>
        <td class="px-4 py-3 text-sm text-gray-600">${inspectionDate}</td>
        <td class="px-4 py-3">
            <button onclick="showPrintModal('${lotNumber}')" 
                    class="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700">
                <i class="fas fa-print mr-1"></i>印刷
            </button>
        </td>
    `;

    return row;
}

function searchPrintItems() {
    const material = document.getElementById('printMaterialFilter')?.value?.toLowerCase() || '';
    const lot = document.getElementById('printLotFilter')?.value?.toLowerCase() || '';

    const rows = document.querySelectorAll('#printItemsTableBody tr');
    let visibleCount = 0;

    rows.forEach(row => {
        const rowMaterial = row.cells[1].textContent.toLowerCase();
        const rowLot = row.cells[2].textContent.toLowerCase();

        const matchMaterial = !material || rowMaterial.includes(material);
        const matchLot = !lot || rowLot.includes(lot);

        if (matchMaterial && matchLot) {
            row.style.display = '';
            visibleCount++;
        } else {
            row.style.display = 'none';
        }
    });
}

function resetPrintFilters() {
    document.getElementById('printMaterialFilter').value = '';
    document.getElementById('printLotFilter').value = '';
    searchPrintItems();
}

async function showPrintModal(lotNumber) {
    currentPrintItemCode = lotNumber;
    currentPrintLotId = null;

    try {
        // ロット番号からアイテム情報を取得
        const response = await fetch(`/api/inventory/search/${encodeURIComponent(lotNumber)}`);
        if (!response.ok) {
            throw new Error('印刷情報の取得に失敗しました');
        }
        const item = await response.json();

        // Lot IDを保存
        currentPrintLotId = item.lot?.id || null;

        // プレビュー情報を表示
        const previewContent = document.getElementById('printPreviewContent');
        previewContent.innerHTML = `
            <div>
                <dt class="font-medium text-gray-500">ロット番号</dt>
                <dd class="text-gray-900 font-mono">${item.lot.lot_number}</dd>
            </div>
            <div>
                <dt class="font-medium text-gray-500">材料名</dt>
                <dd class="text-gray-900">${item.material.display_name}</dd>
            </div>
            <div>
                <dt class="font-medium text-gray-500">形状・寸法</dt>
                <dd class="text-gray-900">${item.material.shape} φ${item.material.diameter_mm}mm</dd>
            </div>
            <div>
                <dt class="font-medium text-gray-500">長さ</dt>
                <dd class="text-gray-900">${item.lot.length_mm}mm</dd>
            </div>
            <div>
                <dt class="font-medium text-gray-500">初期本数</dt>
                <dd class="text-gray-900">${item.lot.initial_quantity ?? '-'}本</dd>
            </div>
            <div>
                <dt class="font-medium text-gray-500">初期重量</dt>
                <dd class="text-gray-900">${item.lot.initial_weight_kg != null ? Number(item.lot.initial_weight_kg).toFixed(3) + 'kg' : '-'}</dd>
            </div>
            <div>
                <dt class="font-medium text-gray-500">現在本数</dt>
                <dd class="text-gray-900">${item.current_quantity}本</dd>
            </div>
            <div>
                <dt class="font-medium text-gray-500">単重</dt>
                <dd class="text-gray-900">${item.weight_per_piece_kg}kg/本</dd>
            </div>
            <div>
                <dt class="font-medium text-gray-500">総重量</dt>
                <dd class="text-gray-900">${(item.lot.initial_weight_kg != null && item.lot.initial_weight_kg > 0) ? `${Number(item.lot.initial_weight_kg).toFixed(3)}kg` : ((item.total_weight_kg != null && item.total_weight_kg > 0) ? `${Number(item.total_weight_kg).toFixed(3)}kg` : '-')}</dd>
            </div>
            <div>
                <dt class="font-medium text-gray-500">置き場</dt>
                <dd class="text-gray-900">${item.location?.name || '未登録'}</dd>
            </div>
            <div>
                <dt class="font-medium text-gray-500">仕入先</dt>
                <dd class="text-gray-900">${item.lot.supplier || '未登録'}</dd>
            </div>
        `;

        document.getElementById('printModal').classList.remove('hidden');

    } catch (error) {
        console.error('印刷モーダル表示エラー:', error);
        if (typeof showToast === 'function') {
            showToast('印刷プレビューの取得に失敗しました', 'error');
        }
    }
}

function hidePrintModal() {
    document.getElementById('printModal').classList.add('hidden');
    currentPrintItemCode = null;
    currentPrintLotId = null;
}

async function executePrintLotNumber() {
    if (!currentPrintLotId) {
        if (typeof showToast === 'function') {
            showToast('ロット情報が取得できません', 'error');
        }
        return;
    }

    // A6用紙に固定
    const labelType = 'a6';
    const copies = parseInt(document.getElementById('printCopies')?.value || '1');

    try {
        const response = await fetch('/api/labels/lot-tag', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lot_id: currentPrintLotId,
                label_type: labelType,
                copies: copies
            })
        });

        if (!response.ok) {
            throw new Error('ロット番号タグ印刷に失敗しました');
        }

        // PDFをダウンロード
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `lot_tag_${currentPrintLotId}_${new Date().getTime()}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        if (typeof showToast === 'function') {
            showToast('ロット番号タグPDFを保存しました', 'success');
        }

        hidePrintModal();

    } catch (error) {
        console.error('ロット番号タグ印刷エラー:', error);
        if (typeof showToast === 'function') {
            showToast('ロット番号タグ印刷に失敗しました: ' + error.message, 'error');
        }
    }
}

// ==== 重量・本数換算機能 ====
function roundTo3(value) {
    return Math.round(value * 1000) / 1000;
}

function calculateUnitWeightKg(shape, diameterMm, lengthMm, density) {
    const lengthCm = lengthMm / 10;
    const base = diameterMm / 10;
    let volumeCm3;

    if (shape === 'round') {
        const radiusCm = base / 2;
        volumeCm3 = Math.PI * radiusCm * radiusCm * lengthCm;
    } else if (shape === 'hexagon') {
        volumeCm3 = (3 * Math.sqrt(3) / 2) * Math.pow(base, 2) * lengthCm;
    } else if (shape === 'square') {
        volumeCm3 = Math.pow(base, 2) * lengthCm;
    } else {
        throw new Error('未対応の形状です');
    }

    return volumeCm3 * density / 1000;
}

function updateConversionDisplays(quantity, weight, unitWeight) {
    const quantityEl = document.getElementById('displayQuantity');
    const weightEl = document.getElementById('displayWeight');
    const unitWeightEl = document.getElementById('displayUnitWeight');

    if (quantityEl) quantityEl.textContent = Number.isFinite(quantity) && quantity > 0 ? String(quantity) : '-';
    if (weightEl) weightEl.textContent = typeof weight === 'number' && Number.isFinite(weight) ? weight.toFixed(3) : '-';
    if (unitWeightEl) unitWeightEl.textContent = typeof unitWeight === 'number' && Number.isFinite(unitWeight) ? unitWeight.toFixed(3) : '-';
}

function clearConversionDisplays() {
    updateConversionDisplays(null, null, null);
}

function updateConversion() {
    try {
        const quantityInput = document.getElementById('quantityInput');
        const weightInput = document.getElementById('weightInput');
        const diameterInput = document.querySelector('input[name="diameter_input"]');
        const densityInput = document.getElementById('densityInput');
        const lengthInput = document.querySelector('input[name="length_mm"]');

        if (!diameterInput || !densityInput || !lengthInput) {
            clearConversionDisplays();
            return;
        }

        const parsedDiameter = parseDiameterInputValue(diameterInput.value || '');
        if (parsedDiameter.error) {
            clearConversionDisplays();
            return;
        }

        const density = parseFloat(densityInput.value);
        const lengthMm = parseInt(lengthInput.value, 10);

        if (!(density > 0) || !(lengthMm > 0)) {
            clearConversionDisplays();
            return;
        }

        const unitWeight = roundTo3(calculateUnitWeightKg(parsedDiameter.shape, parsedDiameter.diameter_mm, lengthMm, density));

        const selectedMethod = document.querySelector('input[name="input_method"]:checked');
        const method = selectedMethod ? selectedMethod.value : 'quantity';

        const quantity = parseInt(quantityInput.value, 10);
        const weight = parseFloat(weightInput.value);

        let displayQuantity = null;
        let displayWeight = null;

        if (method === 'quantity' && Number.isFinite(quantity) && quantity > 0) {
            displayQuantity = quantity;
            displayWeight = roundTo3(unitWeight * quantity);
        } else if (method === 'weight' && Number.isFinite(weight) && weight > 0) {
            displayWeight = weight;
            const computedQuantity = Math.floor(weight / unitWeight);
            displayQuantity = computedQuantity;
        } else if (Number.isFinite(quantity) && quantity > 0) {
            displayQuantity = quantity;
            displayWeight = roundTo3(unitWeight * quantity);
        } else if (Number.isFinite(weight) && weight > 0) {
            displayWeight = weight;
            const computedQuantity = Math.floor(weight / unitWeight);
            displayQuantity = computedQuantity;
        }

        updateConversionDisplays(displayQuantity, displayWeight, unitWeight);
    } catch (error) {
        console.error('換算計算エラー:', error);
        clearConversionDisplays();
    }
}

// テキストエリアの選択範囲をクリップボードへコピー（receiving.jsから移植）
function copySelectionFromTextarea(textareaId) {
    const ta = document.getElementById(textareaId);
    if (!ta) return;
    const start = ta.selectionStart ?? 0;
    const end = ta.selectionEnd ?? start;
    const s = Math.min(start, end);
    const e = Math.max(start, end);
    const text = ta.value.substring(s, e);
    if (!text) {
        // 何も選択されていない場合は全文コピー
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(ta.value);
            if (typeof showToast === 'function') {
                showToast('全文をコピーしました', 'success');
            }
        }
        return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text);
        if (typeof showToast === 'function') {
            showToast('選択範囲をコピーしました', 'success');
        }
    } else {
        const tmp = document.createElement('textarea');
        tmp.value = text;
        document.body.appendChild(tmp);
        tmp.focus();
        tmp.select();
        try { document.execCommand('copy'); } catch (e) { }
        document.body.removeChild(tmp);
    }
}

// ==== 複数ロット管理機能 ====
let lotRowCounter = 0;
let currentOrderedQuantity = 0;
let currentOrderType = 'quantity';

function addLotRow(defaultQuantity = null, defaultWeight = null, defaultLotNumber = '', defaultLocation = '', defaultNotes = '') {
    lotRowCounter++;
    const container = document.getElementById('lotsContainer');
    const rowId = `lot-row-${lotRowCounter}`;
    const counter = lotRowCounter;

    const quantityValue = defaultQuantity && defaultQuantity > 0 ? ` value="${defaultQuantity}"` : '';
    const weightValue = defaultWeight && defaultWeight > 0 ? ` value="${defaultWeight}"` : '';
    const lotNumberValue = defaultLotNumber ? ` value="${defaultLotNumber}"` : '';
    const locationValue = defaultLocation ? ` value="${defaultLocation}"` : '';
    const notesValue = defaultNotes ? ` value="${defaultNotes}"` : '';

    const lotRow = document.createElement('div');
    lotRow.id = rowId;
    lotRow.className = 'bg-white rounded-lg p-4 border-2 border-purple-200';
    lotRow.innerHTML = `
        <div class="flex justify-between items-center mb-3">
            <h4 class="font-medium text-gray-900">ロット ${counter}</h4>
            <button type="button" onclick="removeLotRow('${rowId}')" class="text-red-600 hover:text-red-800 text-sm">
                <i class="fas fa-trash"></i> 削除
            </button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3">
            <div>
                <label class="block text-xs font-medium text-gray-700 mb-1">ロット番号 *</label>
                <input type="text" name="lot_number_${counter}" required
                       class="w-full p-2 border border-gray-300 rounded text-sm"
                       placeholder="例: L001"${lotNumberValue}>
            </div>
            <div>
                <label class="block text-xs font-medium text-gray-700 mb-1">入庫数量（本） *</label>
                <input type="number" name="lot_quantity_${counter}" min="1" step="1"
                       class="lot-quantity-input w-full p-2 border border-gray-300 rounded text-sm"
                       placeholder="本数（必須）"
                       data-lot-id="${counter}"${quantityValue}
                       required
                       oninput="onLotQuantityChange(${counter})">
                <p class="text-xs text-gray-500 mt-1">本数と重量の両方を必ず入力してください</p>
            </div>
            <div>
                <label class="block text-xs font-medium text-gray-700 mb-1">入庫重量（kg） *</label>
                <input type="number" name="lot_weight_${counter}" min="0.001" step="0.001"
                       class="lot-weight-input w-full p-2 border border-gray-300 rounded text-sm"
                       placeholder="重量（必須）"
                       data-lot-id="${counter}"${weightValue}
                       required
                       oninput="onLotWeightChange(${counter})">
                <p class="text-xs text-gray-500 mt-1">重量は必須。本数も必須です。</p>
            </div>
            <div>
                <label class="block text-xs font-medium text-gray-700 mb-1">置き場</label>
                <input type="text" name="lot_location_${counter}"
                       class="w-full p-2 border border-gray-300 rounded text-sm"
                       placeholder="例: 12"${locationValue}>
            </div>
        </div>
        <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">備考</label>
            <input type="text" name="lot_notes_${counter}"
                   class="w-full p-2 border border-gray-300 rounded text-sm"
                   placeholder="このロット固有の備考を入力"${notesValue}>
        </div>
    `;

    container.appendChild(lotRow);
    updateTotalQuantity();
}

function onLotQuantityChange(lotId) {
    const quantityInput = document.querySelector(`input[name="lot_quantity_${lotId}"]`);
    const weightInput = document.querySelector(`input[name="lot_weight_${lotId}"]`);

    // 同時入力を許可するため、相互クリアを廃止
    updateTotalQuantity();
}

function onLotWeightChange(lotId) {
    const quantityInput = document.querySelector(`input[name="lot_quantity_${lotId}"]`);
    const weightInput = document.querySelector(`input[name="lot_weight_${lotId}"]`);

    // 同時入力を許可するため、相互クリアを廃止
    updateTotalQuantity();
}

function removeLotRow(rowId) {
    const row = document.getElementById(rowId);
    if (row) {
        row.remove();
        updateTotalQuantity();
    }
}

function recalculateAmountFromWeight() {
    const unitPriceInput = document.getElementById('unitPriceInput');
    const amountInput = document.getElementById('amountInput');
    if (!unitPriceInput || !amountInput) return;

    const unitPrice = parseFloat(unitPriceInput.value);
    if (!(unitPrice > 0)) {
        amountInput.value = '';
        return;
    }

    // 計算パラメータは「最終的な合計重量」そのもの（ユーザー入力の集計）
    const totalWeightText = document.getElementById('totalWeight')?.textContent || '0';
    const baseWeight = parseFloat(totalWeightText);

    amountInput.value = (Number.isFinite(baseWeight) && baseWeight > 0)
        ? (unitPrice * baseWeight).toFixed(2)
        : '';
}

function updateTotalQuantity() {
    // 計算用パラメータを取得
    const diameterCalcInput = document.getElementById('diameterCalcInput');
    const shapeCalcSelect = document.getElementById('shapeCalcSelect');
    const densityInput = document.getElementById('densityInput');
    const lengthInput = document.querySelector('input[name="length_mm"]');

    let unitWeight = 0;
    if (diameterCalcInput && shapeCalcSelect && densityInput && lengthInput) {
        const diameter_mm = parseFloat(diameterCalcInput.value);
        const shape = shapeCalcSelect.value;
        const density = parseFloat(densityInput.value);
        const lengthMm = parseInt(lengthInput.value, 10);

        if (!isNaN(diameter_mm) && diameter_mm > 0 && shape && density > 0 && lengthMm > 0) {
            try {
                unitWeight = calculateUnitWeightKg(shape, diameter_mm, lengthMm, density);
            } catch (e) {
                unitWeight = 0;
            }
        }
    }

    let totalQuantity = 0;
    let totalWeight = 0;

    // 各ロットの数量と重量を集計
    for (let i = 1; i <= lotRowCounter; i++) {
        const lotRow = document.getElementById(`lot-row-${i}`);
        if (!lotRow) continue;

        const quantityInput = document.querySelector(`input[name="lot_quantity_${i}"]`);
        const weightInput = document.querySelector(`input[name="lot_weight_${i}"]`);

        const quantity = parseInt(quantityInput?.value) || 0;
        const weight = parseFloat(weightInput?.value) || 0;

        // 入力値をそのまま合計に反映（相互換算しない）
        if (quantity > 0) {
            totalQuantity += quantity;
        }
        if (weight > 0) {
            totalWeight += weight;
        }
    }

    // 合計表示を更新（重量はユーザー入力の合計のみを反映）
    document.getElementById('totalQuantity').textContent = totalQuantity;
    document.getElementById('totalWeight').textContent = totalWeight > 0 ? totalWeight.toFixed(3) : '0.000';

    // 参考値の表示（入力方式や注文タイプに応じて片側のみ参照値を反映）
    const qtyRefEl = document.getElementById('totalQuantityRef');
    const weightRefEl = document.getElementById('totalWeightRef');
    const selectedRadio = document.querySelector('input[name="input_method"]:checked');
    const selectedMethod = selectedRadio ? selectedRadio.value : null; // 'quantity' or 'weight'

    if (qtyRefEl) qtyRefEl.textContent = '-';
    if (weightRefEl) weightRefEl.textContent = '-';

    if (unitWeight > 0) {
        // 本数入力モード（または発注タイプが本数）→ 重量（参考）を表示
        if ((selectedMethod === 'quantity' || (!selectedMethod && currentOrderType === 'quantity')) && totalQuantity > 0) {
            if (weightRefEl) weightRefEl.textContent = (unitWeight * totalQuantity).toFixed(3);
        }
        // 重量入力モード（または発注タイプが重量）→ 本数（参考）を表示
        if ((selectedMethod === 'weight' || (!selectedMethod && currentOrderType === 'weight')) && totalWeight > 0) {
            const computedQty = Math.floor(totalWeight / unitWeight);
            if (qtyRefEl) qtyRefEl.textContent = Number.isFinite(computedQty) && computedQty > 0 ? String(computedQty) : '-';
        }
    }

    // 発注数量と比較して色を変更
    const totalEl = document.getElementById('totalQuantity');
    if (currentOrderedQuantity > 0) {
        if (totalQuantity === currentOrderedQuantity) {
            totalEl.classList.remove('text-red-600');
            totalEl.classList.add('text-green-600');
        } else if (totalQuantity > currentOrderedQuantity) {
            totalEl.classList.remove('text-green-600');
            totalEl.classList.add('text-red-600');
        } else {
            totalEl.classList.remove('text-green-600', 'text-red-600');
            totalEl.classList.add('text-purple-600');
        }
    }

    // 合計重量変更に伴い、即座に金額を再計算（単価×合計重量）
    if (typeof recalculateAmountFromWeight === 'function') {
        recalculateAmountFromWeight();
    }
}

function clearLotRows() {
    const container = document.getElementById('lotsContainer');
    if (container) {
        container.innerHTML = '';
    }
    lotRowCounter = 0;
    updateTotalQuantity();
}

// ==== 材料名から径・形状を抽出するユーティリティ関数 ====

/**
 * 材料名から径を抽出
 * @param {string} itemName - 材料名（例: "SUS303 φ10.0 研磨"）
 * @returns {number|null} - 抽出された径（例: 10.0）、見つからない場合は null
 */
function extractDiameterFromName(itemName) {
    if (!itemName) return null;

    // φ10.0, Φ10.0, ∅10.0, H12, □20 などのパターンを検出
    const patterns = [
        /[φΦ∅][\s]*([0-9]+\.?[0-9]*)/,  // 丸棒: φ10.0, Φ10, ∅10.5
        /[Hh][\s]*([0-9]+\.?[0-9]*)/,    // 六角: H12, h12.5
        /[□][\s]*([0-9]+\.?[0-9]*)/      // 角棒: □20, □15.5
    ];

    for (const pattern of patterns) {
        const match = itemName.match(pattern);
        if (match && match[1]) {
            const diameter = parseFloat(match[1]);
            if (!isNaN(diameter) && diameter > 0) {
                return diameter;
            }
        }
    }

    return null;
}

/**
 * 材料名から形状を自動判定
 * @param {string} itemName - 材料名（例: "SUS303 φ10.0 研磨"）
 * @returns {string} - 形状（'round', 'hexagon', 'square'）
 */
function detectShapeFromName(itemName) {
    if (!itemName) return 'round'; // デフォルトは丸棒

    // 六角棒の判定
    if (/[Hh][\s]*[0-9]/.test(itemName) || /六角/.test(itemName)) {
        return 'hexagon';
    }

    // 角棒の判定
    if (/[□][\s]*[0-9]/.test(itemName) || /角棒/.test(itemName) || /四角/.test(itemName)) {
        return 'square';
    }

    // 丸棒の判定（デフォルト）
    return 'round';
}

// ==== ユーティリティ関数 ====
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ================================
// 検品済みロット一覧（検索＋再編集）
// ================================
let inspectedLotsAll = [];
let currentInspectedPage = 1;
const inspectedLotsPageSize = 25;
let inspectedSectionLoaded = false;

async function loadInspectedLotsList(page = 1) {
    const tableBody = document.getElementById('inspectedLotsTableBody');
    const loading = document.getElementById('inspectedLotsLoading');
    const empty = document.getElementById('inspectedLotsEmpty');

    if (!tableBody || !loading || !empty) return;

    loading.classList.remove('hidden');
    tableBody.innerHTML = '';
    empty.classList.add('hidden');

    try {
        const materialSpec = encodeURIComponent((document.getElementById('inspectedMaterialFilter')?.value || '').trim());
        const lotNumber = encodeURIComponent((document.getElementById('inspectedLotFilter')?.value || '').trim());
        const orderNumber = encodeURIComponent((document.getElementById('inspectedOrderNumberFilter')?.value || '').trim());

        const params = [];
        if (materialSpec) params.push(`material_spec=${materialSpec}`);
        if (lotNumber) params.push(`lot_number=${lotNumber}`);
        if (orderNumber) params.push(`order_number=${orderNumber}`);
        params.push('skip=0');
        params.push('limit=1000');

        const url = `/api/inventory/lots/inspected/?${params.join('&')}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        const lots = await res.json();

        loading.classList.add('hidden');

        if (!lots || lots.length === 0) {
            empty.classList.remove('hidden');
            inspectedLotsAll = [];
            renderPagination('inspectedLots', 1, 1, loadInspectedLotsList);
            return;
        }

        inspectedLotsAll = lots;
        const totalPages = Math.ceil(inspectedLotsAll.length / inspectedLotsPageSize);
        currentInspectedPage = Math.min(page, totalPages);
        const startIndex = (currentInspectedPage - 1) * inspectedLotsPageSize;
        const endIndex = startIndex + inspectedLotsPageSize;
        const pageItems = inspectedLotsAll.slice(startIndex, endIndex);

        pageItems.forEach(lot => {
            const row = createInspectedLotRow(lot);
            tableBody.appendChild(row);
        });

        renderPagination('inspectedLots', currentInspectedPage, totalPages, loadInspectedLotsList);
    } catch (error) {
        console.error('検品済み一覧の読み込みに失敗:', error);
        loading.classList.add('hidden');
        if (typeof showToast === 'function') showToast('検品済み一覧の読み込みに失敗しました', 'error');
    }
}

function createInspectedLotRow(lot) {
    const row = document.createElement('tr');
    row.className = 'hover:bg-gray-50';

    const orderNumber = lot.order_number || '-';
    const materialSpec = lot.material_name || '-';
    const lotNumber = lot.lot_number || '-';
    const qty = lot.total_quantity ?? '-';
    const weightDisplay = lot.total_weight_kg > 0 ? `${(lot.total_weight_kg || 0).toFixed(3)}kg` : '-';
    const inspectedAt = lot.inspected_at ? new Date(lot.inspected_at).toLocaleString() : '-';

    const status = (lot.inspection_status || 'pending').toLowerCase();
    let statusText = '未検品';
    let statusClass = 'bg-amber-100 text-amber-700';
    if (status === 'passed') { statusText = '合格'; statusClass = 'bg-green-100 text-green-700'; }
    else if (status === 'failed') { statusText = '不合格'; statusClass = 'bg-red-100 text-red-700'; }

    const btnClass = 'bg-indigo-600 text-white px-2 py-1 rounded text-xs hover:bg-indigo-700';

    row.innerHTML = `
        <td class="px-3 py-2 text-xs text-gray-900">${orderNumber}</td>
        <td class="px-3 py-2 text-xs text-gray-900">${materialSpec}</td>
        <td class="px-3 py-2 text-xs text-gray-900">${lotNumber}</td>
        <td class="px-3 py-2 text-xs text-gray-600">${qty}本</td>
        <td class="px-3 py-2 text-xs text-gray-600">${weightDisplay}</td>
        <td class="px-3 py-2">
            <span class="px-2 py-1 rounded-full text-xs font-medium ${statusClass}">${statusText}</span>
        </td>
        <td class="px-3 py-2 text-xs text-gray-600">${inspectedAt}</td>
        <td class="px-3 py-2">
            <button class="${btnClass}" onclick="editInspectedLot('${lotNumber}')">再編集</button>
        </td>
    `;
    return row;
}

function editInspectedLot(lotNumber) {
    const codeInput = document.getElementById('inspectionCodeInput');
    if (codeInput) codeInput.value = lotNumber;
    loadInspectionTargetByCode();
    const form = document.getElementById('inspectionForm');
    form?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function toggleInspectedSection() {
    const section = document.getElementById('inspectedLotsSection');
    const btn = document.getElementById('toggleInspectedSectionBtn');
    if (!section || !btn) return;
    if (section.classList.contains('hidden')) {
        section.classList.remove('hidden');
        btn.textContent = '閉じる';
        if (!inspectedSectionLoaded) {
            loadInspectedLotsList(1);
            inspectedSectionLoaded = true;
        }
    } else {
        section.classList.add('hidden');
        btn.textContent = '開く';
    }
}

/**
 * ページネーションUIを生成して表示
 * @param {string} prefix - ページネーションの識別子（'orders', 'receiving', 'inspection'）
 * @param {number} currentPage - 現在のページ番号
 * @param {number} totalPages - 総ページ数
 * @param {Function} loadFunc - ページロード関数
 */
function renderPagination(prefix, currentPage, totalPages, loadFunc) {
    const topContainer = document.getElementById(`${prefix}PaginationTop`);
    const bottomContainer = document.getElementById(`${prefix}PaginationBottom`);

    if (!topContainer || !bottomContainer) {
        console.warn(`ページネーションコンテナが見つかりません: ${prefix}`);
        return;
    }

    // ページネーションHTMLを生成
    const paginationHTML = createPaginationHTML(currentPage, totalPages, loadFunc);

    // 上部と下部に同じページネーションを表示
    topContainer.innerHTML = paginationHTML;
    bottomContainer.innerHTML = paginationHTML;
}

/**
 * ページネーションHTMLを生成
 * @param {number} currentPage - 現在のページ番号
 * @param {number} totalPages - 総ページ数
 * @param {Function} loadFunc - ページロード関数
 * @returns {string} ページネーションHTML
 */
function createPaginationHTML(currentPage, totalPages, loadFunc) {
    if (totalPages <= 1) {
        return '';
    }

    const funcName = loadFunc.name;
    let html = '<div class="flex items-center justify-between bg-white rounded-lg p-3 border border-gray-200">';

    // ページ情報
    html += `<div class="text-sm text-gray-700">
        ページ <span class="font-medium">${currentPage}</span> / <span class="font-medium">${totalPages}</span>
    </div>`;

    // ページネーションボタン
    html += '<div class="flex items-center space-x-2">';

    // 最初へ
    if (currentPage > 1) {
        html += `<button onclick="${funcName}(1)" class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm">
            <i class="fas fa-angle-double-left"></i>
        </button>`;
    } else {
        html += `<button disabled class="px-3 py-1 border border-gray-300 rounded bg-gray-100 text-gray-400 cursor-not-allowed text-sm">
            <i class="fas fa-angle-double-left"></i>
        </button>`;
    }

    // 前へ
    if (currentPage > 1) {
        html += `<button onclick="${funcName}(${currentPage - 1})" class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm">
            <i class="fas fa-angle-left"></i>
        </button>`;
    } else {
        html += `<button disabled class="px-3 py-1 border border-gray-300 rounded bg-gray-100 text-gray-400 cursor-not-allowed text-sm">
            <i class="fas fa-angle-left"></i>
        </button>`;
    }

    // ページ番号ボタン（最大7個表示）
    const pageButtons = getPageNumbers(currentPage, totalPages);
    pageButtons.forEach(pageNum => {
        if (pageNum === '...') {
            html += `<span class="px-2 text-gray-500">...</span>`;
        } else {
            if (pageNum === currentPage) {
                html += `<button class="px-3 py-1 bg-blue-600 text-white rounded font-medium text-sm">${pageNum}</button>`;
            } else {
                html += `<button onclick="${funcName}(${pageNum})" class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm">${pageNum}</button>`;
            }
        }
    });

    // 次へ
    if (currentPage < totalPages) {
        html += `<button onclick="${funcName}(${currentPage + 1})" class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm">
            <i class="fas fa-angle-right"></i>
        </button>`;
    } else {
        html += `<button disabled class="px-3 py-1 border border-gray-300 rounded bg-gray-100 text-gray-400 cursor-not-allowed text-sm">
            <i class="fas fa-angle-right"></i>
        </button>`;
    }

    // 最後へ
    if (currentPage < totalPages) {
        html += `<button onclick="${funcName}(${totalPages})" class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 text-sm">
            <i class="fas fa-angle-double-right"></i>
        </button>`;
    } else {
        html += `<button disabled class="px-3 py-1 border border-gray-300 rounded bg-gray-100 text-gray-400 cursor-not-allowed text-sm">
            <i class="fas fa-angle-double-right"></i>
        </button>`;
    }

    html += '</div></div>';

    return html;
}

/**
 * 表示するページ番号の配列を取得
 * @param {number} current - 現在のページ
 * @param {number} total - 総ページ数
 * @returns {Array} ページ番号配列（'...'を含む）
 */
function getPageNumbers(current, total) {
    if (total <= 7) {
        return Array.from({ length: total }, (_, i) => i + 1);
    }

    // 現在ページが先頭付近
    if (current <= 4) {
        return [1, 2, 3, 4, 5, '...', total];
    }

    // 現在ページが末尾付近
    if (current >= total - 3) {
        return [1, '...', total - 4, total - 3, total - 2, total - 1, total];
    }

    // 現在ページが中央
    return [1, '...', current - 1, current, current + 1, '...', total];
}

// ==== 処理タブ（2025-11-06追加） ====
const PROCESSING_OPTIONS = [
    "片側面取り",
    "両側面取り",
    "段挽きφ36",
    "段挽きφ30",
    "段挽きφ18",
    "段挽きφ10",
    "梱包剥き"
];

function initializeProcessingTab() {
    const refreshBtn = document.getElementById('refreshProcessingBtn');
    const showCompletedCheckbox = document.getElementById('showCompletedProcessing');
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadProcessingItems);
    }
    if (showCompletedCheckbox) {
        showCompletedCheckbox.addEventListener('change', loadProcessingItems);
    }
}

async function loadProcessingItems() {
    const tbody = document.getElementById('processingItemsTableBody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td class="px-3 py-2 text-gray-500" colspan="11">読み込み中...</td></tr>';
    
    const showCompleted = document.getElementById('showCompletedProcessing')?.checked || false;
    const url = `/api/purchase-orders/processing-items/?show_completed=${showCompleted}`;
    
    try {
        const resp = await fetch(url, { method: 'GET' });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        const items = data.items || [];
        tbody.innerHTML = '';
        
        if (items.length === 0) {
            tbody.innerHTML = '<tr><td class="px-3 py-2 text-gray-500 text-center" colspan="11">データがありません</td></tr>';
            return;
        }
        
        for (const row of items) {
            const tr = document.createElement('tr');
            const isCompleted = row.is_completed;
            
            const selectId = `proc-select-${row.id}`;
            const notesId  = `proc-notes-${row.id}`;
            const workerId = `proc-worker-${row.id}`;
            const saveId   = `proc-save-${row.id}`;
            const actionId = `proc-action-${row.id}`;

            const statusBadge = isCompleted 
                ? '<span class="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">完了</span>'
                : '<span class="px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs font-medium">未完了</span>';
            
            const actionButton = isCompleted
                ? `<button id="${actionId}" class="px-2 py-1 bg-amber-600 text-white rounded hover:bg-amber-700 text-sm">再編集</button>`
                : `<button id="${actionId}" class="px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm">完了</button>`;

            const disabledAttr = isCompleted ? 'disabled' : '';
            const disabledClass = isCompleted ? 'bg-gray-100 cursor-not-allowed' : '';
            const rawFreeText = row.free_text ?? '';
            const hasFreeText = rawFreeText.trim().length > 0;
            const rawInstruction = row.processing_instruction ?? '';
            const instructionValue = hasFreeText ? '' : rawInstruction;
            const optionList = PROCESSING_OPTIONS.slice();
            if (instructionValue && !optionList.includes(instructionValue)) {
                optionList.push(instructionValue);
            }
            const optionsHtml = [
                `<option value="" ${instructionValue === '' ? 'selected' : ''}>未入力</option>`,
                ...optionList.map(opt => `<option value="${opt}" ${instructionValue === opt ? 'selected' : ''}>${opt}</option>`)
            ].join('');

            tr.innerHTML = `
                <td class="px-3 py-2">${row.order_number || ''}</td>
                <td class="px-3 py-2">${row.lot_number || row.lot_id}</td>
                <td class="px-3 py-2">${row.material_name || ''}</td>
                <td class="px-3 py-2 text-right">${row.quantity ?? 0}</td>
                <td class="px-3 py-2">${formatDateToJP(row.set_scheduled_date)}</td>
                <td class="px-3 py-2">${row.machine_no || '-'}</td>
                <td class="px-3 py-2">
                    <select id="${selectId}" class="border rounded px-2 py-1 text-sm ${disabledClass}" ${disabledAttr}>
                        ${optionsHtml}
                    </select>
                </td>
                <td class="px-3 py-2">
                    <input id="${notesId}" type="text" class="border rounded px-2 py-1 text-sm w-56 ${disabledClass}"
                           placeholder="自由入力" value="${rawFreeText}" ${disabledAttr}>
                </td>
                <td class="px-3 py-2">
                    <input id="${workerId}" type="text" class="border rounded px-2 py-1 text-sm w-40 ${disabledClass}"
                           placeholder="作業者" value="${row.processed_by ?? ''}" autocomplete="on" ${disabledAttr}>
                </td>
                <td class="px-3 py-2 text-center">${statusBadge}</td>
                <td class="px-3 py-2 text-center">
                    <div class="flex gap-2 justify-center">
                        <button id="${saveId}" class="px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700 text-sm" ${disabledAttr}>保存</button>
                        ${actionButton}
                    </div>
                </td>
            `;
            tbody.appendChild(tr);

            const selectEl = document.getElementById(selectId);
            const notesEl  = document.getElementById(notesId);
            const workerEl = document.getElementById(workerId);
            const saveEl   = document.getElementById(saveId);
            const actionEl = document.getElementById(actionId);

            let syncNotesState = () => {};
            if (selectEl && notesEl) {
                syncNotesState = (clearOnSelect = false) => {
                    const hasSelection = selectEl.value !== '';
                    if (hasSelection) {
                        if (clearOnSelect) {
                            notesEl.value = '';
                        }
                        notesEl.disabled = true;
                        notesEl.classList.add('bg-gray-100', 'cursor-not-allowed');
                    } else if (!selectEl.disabled) {
                        notesEl.disabled = false;
                        notesEl.classList.remove('bg-gray-100', 'cursor-not-allowed');
                    }
                };

                syncNotesState();

                selectEl.addEventListener('change', () => syncNotesState(true));
                notesEl.addEventListener('input', () => {
                    if (notesEl.value.trim() !== '' && selectEl.value !== '') {
                        selectEl.value = '';
                    }
                    syncNotesState();
                });
            }

            saveEl.addEventListener('click', async () => {
                if (isCompleted) return;
                saveEl.disabled = true;
                saveEl.textContent = '保存中...';
                try {
                    const resp = await fetch(`/api/purchase-orders/processing-items/${row.id}?instruction=${encodeURIComponent(selectEl.value)}&free_text=${encodeURIComponent(notesEl.value || '')}&worker=${encodeURIComponent(workerEl.value || '')}`, {
                        method: 'PUT'
                    });
                    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                    if (typeof showToast === 'function') {
                        showToast('処理情報を保存しました', 'success');
                    }
                } catch (e) {
                    console.error(e);
                    alert('保存に失敗しました');
                } finally {
                    saveEl.disabled = false;
                    saveEl.textContent = '保存';
                }
            });

            actionEl.addEventListener('click', async () => {
                if (isCompleted) {
                    // 再編集モード
                    selectEl.disabled = false;
                    selectEl.classList.remove('bg-gray-100', 'cursor-not-allowed');
                    notesEl.disabled = false;
                    notesEl.classList.remove('bg-gray-100', 'cursor-not-allowed');
                    workerEl.disabled = false;
                    workerEl.classList.remove('bg-gray-100', 'cursor-not-allowed');
                    saveEl.disabled = false;

                    syncNotesState();
                    
                    actionEl.textContent = '完了';
                    actionEl.classList.remove('bg-amber-600', 'hover:bg-amber-700');
                    actionEl.classList.add('bg-blue-600', 'hover:bg-blue-700');
                    
                    // 状態バッジを未完了に変更
                    const statusCell = tr.cells[9];
                    statusCell.innerHTML = '<span class="px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs font-medium">未完了</span>';
                    
                    if (typeof showToast === 'function') {
                        showToast('再編集モードにしました', 'info');
                    }
                } else {
                    // 完了処理
                    if (!confirm('このアイテムを完了にしますか？')) return;
                    actionEl.disabled = true;
                    actionEl.textContent = '完了中...';
                    try {
                        const resp = await fetch(`/api/purchase-orders/processing-items/${row.id}/complete`, {
                            method: 'POST'
                        });
                        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                        if (typeof showToast === 'function') {
                            showToast('処理完了にしました', 'success');
                        }
                        
                        const showCompleted = document.getElementById('showCompletedProcessing')?.checked || false;
                        if (!showCompleted) {
                            tr.remove();
                        } else {
                            loadProcessingItems();
                        }
                    } catch (e) {
                        console.error(e);
                        alert('完了処理に失敗しました');
                        actionEl.disabled = false;
                        actionEl.textContent = '完了';
                    }
                }
            });
        }
    } catch (e) {
        console.error(e);
        tbody.innerHTML = '<tr><td class="px-3 py-2 text-red-600" colspan="11">読み込みに失敗しました</td></tr>';
    }
}
