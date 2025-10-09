// 発注フロー統合ページの主要機能

// ==== タブ切り替え機能 ====
document.addEventListener('DOMContentLoaded', function () {
    initializeTabs();
    initializeImportTab();
    initializeOrdersTab();
    initializeReceivingTab();
    initializeInspectionTab();
    initializePrintTab();
});

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
    document.getElementById('refreshReceivingBtn')?.addEventListener('click', loadReceivingItems);
    document.getElementById('resetReceivingFiltersBtn')?.addEventListener('click', resetReceivingFilters);
    document.getElementById('includeInspectedFilter')?.addEventListener('change', loadReceivingItems);

    // リアルタイム検索（入力時にdebounceで検索実行）
    document.getElementById('receivingOrderNumberFilter')?.addEventListener('input', debounce(() => searchReceivingItems(), 300));
    document.getElementById('receivingSupplierFilter')?.addEventListener('input', debounce(() => searchReceivingItems(), 300));
    document.getElementById('receivingMaterialFilter')?.addEventListener('input', debounce(() => searchReceivingItems(), 300));

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

        // 単価×数量で自動計算（単価が入力された場合）
        // 発注タイプに応じて数量または重量を使用
        if (unitPriceInput) {
            const calculateAmount = function () {
                const unitPrice = parseFloat(unitPriceInput.value);
                if (isNaN(unitPrice) || unitPrice <= 0) return;

                let calculationBase = 0;
                if (item.order_type === 'quantity' && item.ordered_quantity) {
                    calculationBase = item.ordered_quantity;
                } else if (item.order_type === 'weight' && item.ordered_weight_kg) {
                    calculationBase = item.ordered_weight_kg;
                }

                if (calculationBase > 0 && amountInput) {
                    amountInput.value = (unitPrice * calculationBase).toFixed(2);
                }
            };

            unitPriceInput.addEventListener('input', calculateAmount);
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

        // 選択イベントを設定
        selectElement.onchange = function () {
            const densityInput = document.getElementById('densityInput');
            if (this.value && densityInput) {
                densityInput.value = this.value;

                // 選択したプリセット名をトーストで通知
                const selectedOption = this.options[this.selectedIndex];
                if (selectedOption && selectedOption.dataset.name && typeof showToast === 'function') {
                    showToast(`比重プリセット「${selectedOption.dataset.name}」を適用しました`, 'success');
                }

                // 合計を更新
                if (typeof updateTotalQuantity === 'function') {
                    updateTotalQuantity();
                }
            }
        };

    } catch (error) {
        console.error('比重プリセット読み込みエラー:', error);
    }
}

async function handleReceive(event) {
    event.preventDefault();

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

        if (!quantity && !weight) {
            if (typeof showToast === 'function') {
                showToast(`ロット ${i}: 数量または重量を入力してください`, 'error');
            }
            return;
        }

        const lotData = {
            lot_number: lotNumber.trim(),
            location_id: location && location.trim() !== '' ? parseInt(location) : null,
            purchase_month: purchaseMonth,
            notes: lotNotes.trim() || null
        };

        // 数量または重量を設定
        if (quantity) {
            lotData.received_quantity = parseInt(quantity);
        } else if (weight) {
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

    // 合計数量チェック（本数指定のロットのみ）
    const totalQuantity = lots.reduce((sum, lot) => sum + (lot.received_quantity || 0), 0);
    if (currentOrderedQuantity > 0 && totalQuantity > 0 && totalQuantity !== currentOrderedQuantity) {
        const confirmMsg = `合計数量（${totalQuantity}本）が発注数量（${currentOrderedQuantity}本）と一致しません。このまま登録しますか？`;
        if (!confirm(confirmMsg)) {
            return;
        }
    }

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

            // 数量または重量を設定
            if (lot.received_quantity) {
                receiveData.received_quantity = lot.received_quantity;
            } else if (lot.received_weight_kg) {
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
        // 入庫済みアイテムを取得（limit=1000で取得）
        const response = await fetch('/api/inventory/?skip=0&limit=1000&is_active=true&has_stock=true');
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const items = await response.json();

        console.log('取得したアイテム数:', items.length); // デバッグ用
        console.log('最初のアイテムのデータ構造:', items[0]); // デバッグ用

        loading.classList.add('hidden');

        // 入庫済み（lot情報あり）のアイテムのみフィルタ
        const validItems = Array.isArray(items)
            ? items.filter(item => {
                const hasLot = item.lot && item.lot.id && item.lot.lot_number;

                if (!hasLot) {
                    console.warn('ロット情報がないアイテム:', item.id, item);
                }

                return hasLot;
            })
            : [];

        console.log('有効なアイテム数:', validItems.length); // デバッグ用

        if (validItems.length === 0) {
            empty.classList.remove('hidden');
            inspectionAllItems = [];
            return;
        }

        // 全アイテムを保存
        inspectionAllItems = validItems;

        // ページネーション処理
        const totalPages = Math.ceil(inspectionAllItems.length / inspectionPageSize);
        currentInspectionPage = Math.min(page, totalPages);
        const startIndex = (currentInspectionPage - 1) * inspectionPageSize;
        const endIndex = startIndex + inspectionPageSize;
        const pageItems = inspectionAllItems.slice(startIndex, endIndex);

        pageItems.forEach(item => {
            const row = createInspectionItemRow(item);
            tableBody.appendChild(row);
        });

        // ページネーション表示
        renderPagination('inspection', currentInspectionPage, totalPages, loadInspectionItemsList);

    } catch (error) {
        loading.classList.add('hidden');
        console.error('入庫済みアイテム読み込みエラー:', error);
        if (typeof showToast === 'function') {
            showToast('入庫済みアイテムの読み込みに失敗しました: ' + error.message, 'error');
        }
    }
}

function createInspectionItemRow(item) {
    const row = document.createElement('tr');
    row.className = 'hover:bg-gray-50';

    // 材料仕様はExcelから取得したフルネーム（display_name）を表示
    const materialSpec = item.material?.display_name || item.material?.name || '-';

    const lotNumber = item.lot?.lot_number || '-';
    const managementCode = item.management_code || '';
    const lotNotes = item.lot?.notes || '-';

    // 重量計算
    const totalWeight = item.total_weight_kg || 0;
    const weightDisplay = totalWeight > 0 ? `${totalWeight.toFixed(3)}kg` : '-';

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
        const res = await fetch(`/api/inventory/search/${encodeURIComponent(lotNumber)}`);
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
            const weight = item?.total_weight_kg ? `${item.total_weight_kg.toFixed(3)}kg` : '-';
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
    const measuredValStr = document.getElementById('measuredValueInput').value;
    const appearanceOk = document.getElementById('appearanceOkInput').checked;
    const bendingOk = document.getElementById('bendingOkInput').checked;
    const inspectedBy = document.getElementById('inspectedByInput').value.trim();
    const notes = document.getElementById('inspectionNotesInput').value.trim();

    // 検品ステータスを判定（両方OKなら合格、それ以外は不合格）
    const inspectionStatus = appearanceOk && bendingOk ? 'passed' : 'failed';

    const payload = {
        inspection_status: inspectionStatus,
        inspected_at: inspectedAtStr ? new Date(inspectedAtStr).toISOString() : new Date().toISOString(),
        measured_value: measuredValStr ? parseFloat(measuredValStr) : null,
        appearance_ok: appearanceOk,
        bending_ok: bendingOk,
        inspected_by_name: inspectedBy || null,
        inspection_notes: notes || null
    };

    console.log('検品データペイロード:', payload); // デバッグ

    try {
        const url = `/api/inventory/lots/${currentInspectionLotId}/inspection/`;
        console.log('検品API URL:', url); // デバッグ

        const res = await fetch(url, {
            method: 'PUT',
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
                <dt class="font-medium text-gray-500">現在本数</dt>
                <dd class="text-gray-900">${item.current_quantity}本</dd>
            </div>
            <div>
                <dt class="font-medium text-gray-500">単重</dt>
                <dd class="text-gray-900">${item.weight_per_piece_kg}kg/本</dd>
            </div>
            <div>
                <dt class="font-medium text-gray-500">総重量</dt>
                <dd class="text-gray-900">${item.total_weight_kg}kg</dd>
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

    const labelType = document.getElementById('printLabelType')?.value || 'standard';
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
            displayWeight = roundTo3(weight);
            const computedQuantity = Math.max(1, Math.round(weight / unitWeight));
            displayQuantity = computedQuantity;
        } else if (Number.isFinite(quantity) && quantity > 0) {
            displayQuantity = quantity;
            displayWeight = roundTo3(unitWeight * quantity);
        } else if (Number.isFinite(weight) && weight > 0) {
            displayWeight = roundTo3(weight);
            const computedQuantity = Math.max(1, Math.round(weight / unitWeight));
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
                <label class="block text-xs font-medium text-gray-700 mb-1">入庫数量（本）</label>
                <input type="number" name="lot_quantity_${counter}" min="1" step="1"
                       class="lot-quantity-input w-full p-2 border border-gray-300 rounded text-sm"
                       placeholder="本数"
                       data-lot-id="${counter}"${quantityValue}
                       oninput="onLotQuantityChange(${counter})">
                <p class="text-xs text-gray-500 mt-1">または重量</p>
            </div>
            <div>
                <label class="block text-xs font-medium text-gray-700 mb-1">入庫重量（kg）</label>
                <input type="number" name="lot_weight_${counter}" min="0.001" step="0.001"
                       class="lot-weight-input w-full p-2 border border-gray-300 rounded text-sm"
                       placeholder="重量"
                       data-lot-id="${counter}"${weightValue}
                       oninput="onLotWeightChange(${counter})">
                <p class="text-xs text-gray-500 mt-1">どちらか入力</p>
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

    if (quantityInput && quantityInput.value && weightInput) {
        // 本数入力時は重量をクリア
        weightInput.value = '';
    }

    updateTotalQuantity();
}

function onLotWeightChange(lotId) {
    const quantityInput = document.querySelector(`input[name="lot_quantity_${lotId}"]`);
    const weightInput = document.querySelector(`input[name="lot_weight_${lotId}"]`);

    if (weightInput && weightInput.value && quantityInput) {
        // 重量入力時は本数をクリア
        quantityInput.value = '';
    }

    updateTotalQuantity();
}

function removeLotRow(rowId) {
    const row = document.getElementById(rowId);
    if (row) {
        row.remove();
        updateTotalQuantity();
    }
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

        if (quantity > 0) {
            totalQuantity += quantity;
            if (unitWeight > 0) {
                totalWeight += quantity * unitWeight;
            }
        } else if (weight > 0) {
            totalWeight += weight;
            if (unitWeight > 0) {
                totalQuantity += Math.round(weight / unitWeight);
            }
        }
    }

    // 合計表示を更新
    document.getElementById('totalQuantity').textContent = totalQuantity;
    document.getElementById('totalWeight').textContent = totalWeight > 0 ? totalWeight.toFixed(3) : '0.000';

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
