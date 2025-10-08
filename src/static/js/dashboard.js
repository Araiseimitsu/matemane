class DashboardPage {
    constructor() {
        this.state = {
            inventory: [],
            materialsCount: null,
            groups: [],
            movements: [],
            alerts: [],
            forecasts: [],
            pendingPO: [],
            lastInventoryRefresh: null,
        };

        this.elements = {
            totalInventory: document.getElementById("total-inventory"),
            groupCount: document.getElementById("group-count"),
            materialTypes: document.getElementById("material-types"),
            lastInventoryRefresh: document.getElementById("last-inventory-refresh"),
            pendingPOCount: document.getElementById("pending-po-count"),
            pendingPOWeight: document.getElementById("pending-po-weight"),
            forecastRiskCount: document.getElementById("forecast-risk-count"),
            nearestStockout: document.getElementById("nearest-stockout"),
            groupSnapshot: document.getElementById("groupSnapshot"),
            pendingPOList: document.getElementById("pendingPOList"),
            stockAlerts: document.getElementById("stock-alerts"),
            recentActivities: document.getElementById("recent-activities"),
            stockoutForecast: document.getElementById("stockout-forecast"),
            refreshBtn: document.getElementById("refreshDashboard"),
            refreshStatus: document.getElementById("refresh-status"),
        };

        this.init();
    }

    init() {
        this.bindEvents();
        this.loadAll();
        this.startAutoRefresh();
    }

    bindEvents() {
        if (this.elements.refreshBtn) {
            this.elements.refreshBtn.addEventListener("click", () => this.loadAll());
        }
    }

    startAutoRefresh() {
        // 5分ごとに自動更新
        setInterval(() => {
            this.loadAll();
        }, 5 * 60 * 1000);
    }

    async loadAll() {
        this.setRefreshState(true);
        try {
            const [inventoryGroups, materialsCount, inventoryItems, recentMovements, stockAlerts, forecasts, pendingPOItems] = await Promise.all([
                APIClient.getInventoryGroups({ include_inactive_groups: false }),
                APIClient.getMaterialsCount({ is_active: true }),
                APIClient.getInventory({ limit: 20, has_stock: true, include_zero_stock: false }),
                APIClient.getMovements({ limit: 10 }),
                APIClient.getLowStockItems(5),
                APIClient.getStockoutForecast(),
                APIClient.getPendingPurchaseItems(false),
            ]);

            this.state.groups = inventoryGroups;
            this.state.materialsCount = materialsCount?.total ?? null;
            this.state.inventory = inventoryItems ?? [];
            this.state.movements = recentMovements ?? [];
            this.state.alerts = stockAlerts?.items ?? [];
            this.state.forecasts = forecasts ?? [];
            this.state.pendingPO = pendingPOItems ?? [];
            this.state.lastInventoryRefresh = new Date();

            this.render();
        } catch (error) {
            console.error("Dashboard load error", error);
            Utils.showToast(error.message || "ダッシュボードの更新に失敗しました", "error");
        } finally {
            this.setRefreshState(false);
        }
    }

    setRefreshState(loading) {
        if (this.elements.refreshBtn) {
            this.elements.refreshBtn.disabled = loading;
            const icon = this.elements.refreshBtn.querySelector('i');
            if (icon) {
                if (loading) {
                    icon.classList.add('fa-spin');
                } else {
                    icon.classList.remove('fa-spin');
                }
            }
        }
        if (this.elements.refreshStatus) {
            this.elements.refreshStatus.textContent = loading ? "更新中..." : "システム稼働中";
        }
    }

    render() {
        this.renderInventorySummary();
        this.renderGroupSnapshot();
        this.renderPendingPO();
        this.renderStockAlerts();
        this.renderRecentMovements();
        this.renderForecasts();
    }

    // カウントアップアニメーション
    animateCounter(element, targetValue, duration = 1000, decimals = 0) {
        if (!element) return;

        const startValue = parseFloat(element.textContent.replace(/[^0-9.-]/g, '')) || 0;
        const startTime = performance.now();

        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // イージング関数（easeOutExpo）
            const easeProgress = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
            const currentValue = startValue + (targetValue - startValue) * easeProgress;

            element.textContent = Utils.formatNumber(currentValue, decimals);

            if (progress < 1) {
                requestAnimationFrame(animate);
            } else {
                element.textContent = Utils.formatNumber(targetValue, decimals);
            }
        };

        requestAnimationFrame(animate);
    }

    renderInventorySummary() {
        const totalQuantity = this.state.groups.reduce((sum, group) => sum + (group.total_stock || 0), 0);
        const activeGroupCount = this.state.groups.length;
        const materialCount = typeof this.state.materialsCount === "number" ? this.state.materialsCount : null;

        // カウントアップアニメーション適用
        if (this.elements.totalInventory) {
            this.animateCounter(this.elements.totalInventory, totalQuantity, 1200);
        }
        if (this.elements.groupCount) {
            this.elements.groupCount.textContent = `${Utils.formatNumber(activeGroupCount)} グループ`;
        }
        if (this.elements.materialTypes) {
            if (materialCount != null) {
                this.animateCounter(this.elements.materialTypes, materialCount, 1000);
            } else {
                this.elements.materialTypes.textContent = "-";
            }
        }
        if (this.elements.lastInventoryRefresh) {
            if (this.state.lastInventoryRefresh) {
                this.elements.lastInventoryRefresh.textContent = this.state.lastInventoryRefresh.toLocaleString("ja-JP", {
                    hour: "2-digit",
                    minute: "2-digit",
                });
            } else {
                this.elements.lastInventoryRefresh.textContent = "-";
            }
        }
    }

    renderGroupSnapshot() {
        if (!this.elements.groupSnapshot) return;

        if (!this.state.groups.length) {
            this.elements.groupSnapshot.innerHTML = `
                <div class="text-center py-12">
                    <div class="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-gray-100 to-gray-200 rounded-full mb-6 shadow-inner">
                        <i class="fas fa-box-open text-3xl text-gray-400"></i>
                    </div>
                    <p class="text-sm font-semibold text-gray-600">在庫グループが見つかりませんでした</p>
                </div>
            `;
            return;
        }

        const topGroups = [...this.state.groups]
            .filter(group => (group.total_stock || 0) > 0)
            .sort((a, b) => (b.total_stock || 0) - (a.total_stock || 0))
            .slice(0, 5);

        this.elements.groupSnapshot.innerHTML = topGroups.map((group, index) => `
            <div class="glass-card border border-indigo-200 rounded-2xl p-5 hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1"
                 style="animation: slideInUp 0.4s ease-out ${index * 0.1}s both;">
                <div class="flex items-center justify-between">
                    <div class="flex-1">
                        <p class="text-sm font-bold text-gray-900 mb-2">${group.group_name}</p>
                        <div class="flex items-center space-x-3 text-xs text-gray-600">
                            <span class="inline-flex items-center px-2 py-1 bg-indigo-50 rounded-lg">
                                <i class="fas fa-cubes mr-1"></i> ${group.materials.length} 材料
                            </span>
                            <span class="inline-flex items-center px-2 py-1 bg-purple-50 rounded-lg">
                                <i class="fas fa-layer-group mr-1"></i> ${group.lot_count} ロット
                            </span>
                        </div>
                    </div>
                    <div class="text-right ml-4">
                        <div class="text-2xl font-black bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                            ${Utils.formatNumber(group.total_stock)}
                        </div>
                        <div class="text-xs text-gray-500 font-semibold">本</div>
                    </div>
                </div>
                <div class="mt-3 pt-3 border-t border-gray-100">
                    <p class="text-xs text-gray-500 truncate">${group.materials.map(m => m.name).join(", ")}</p>
                </div>
            </div>
        `).join("");
    }

    renderPendingPO() {
        if (!this.elements.pendingPOList) return;

        if (!this.state.pendingPO.length) {
            this.elements.pendingPOList.innerHTML = `
                <div class="text-center py-12">
                    <div class="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-green-400 to-emerald-500 rounded-full mb-6 shadow-lg">
                        <i class="fas fa-clipboard-check text-3xl text-white"></i>
                    </div>
                    <p class="text-sm font-bold text-gray-800">入庫待ち・検品待ちはありません</p>
                    <p class="text-xs text-gray-500 mt-2">すべての発注が処理されています</p>
                </div>
            `;
            this.updatePendingPOSummary();
            return;
        }

        const totalWeight = this.state.pendingPO.reduce((sum, item) => sum + (item.ordered_weight_kg || 0), 0);
        this.updatePendingPOSummary(this.state.pendingPO.length, totalWeight);

        const topPending = this.state.pendingPO.slice(0, 5);
        this.elements.pendingPOList.innerHTML = topPending.map((item, index) => `
            <div class="glass-card border border-amber-200 rounded-2xl p-5 hover:shadow-xl hover:border-amber-400 transition-all duration-300"
                 style="animation: slideInUp 0.4s ease-out ${index * 0.1}s both;">
                <div class="flex items-center justify-between">
                    <div class="flex-1">
                        <p class="text-sm font-bold text-gray-900 mb-2">${item.item_name}</p>
                        <p class="text-xs text-gray-500">
                            <i class="fas fa-receipt mr-1"></i>発注番号: ${item.purchase_order?.order_number ?? "-"}
                        </p>
                    </div>
                    <div class="text-right ml-4">
                        <div class="text-lg font-black text-amber-700">
                            ${item.ordered_quantity ? `${Utils.formatNumber(item.ordered_quantity)} 本` : "-"}
                        </div>
                        <div class="text-xs text-gray-600 font-semibold">
                            ${item.ordered_weight_kg ? `${Utils.formatNumber(item.ordered_weight_kg, 1)} kg` : "-"}
                        </div>
                    </div>
                </div>
            </div>
        `).join("");
    }

    updatePendingPOSummary(count = 0, weight = 0) {
        if (this.elements.pendingPOCount) {
            this.animateCounter(this.elements.pendingPOCount, count, 1000);
        }
        if (this.elements.pendingPOWeight) {
            this.elements.pendingPOWeight.textContent = weight ? `${Utils.formatNumber(weight, 1)} kg` : "- kg";
        }
    }

    renderStockAlerts() {
        if (!this.elements.stockAlerts) return;

        if (!this.state.alerts.length) {
            this.elements.stockAlerts.innerHTML = `
                <div class="text-center py-12">
                    <div class="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-green-400 to-emerald-500 rounded-full mb-6 shadow-lg">
                        <i class="fas fa-check-circle text-4xl text-white"></i>
                    </div>
                    <p class="text-gray-800 font-bold text-lg">現在アラートはありません</p>
                    <p class="text-sm text-gray-600 mt-2 font-medium">在庫状況は正常です</p>
                </div>
            `;
            return;
        }

        this.elements.stockAlerts.innerHTML = this.state.alerts.slice(0, 6).map((alert, index) => {
            const levelClass = alert.alert_level === "危険"
                ? "border-red-300 bg-gradient-to-br from-red-50 to-rose-100"
                : alert.alert_level === "注意"
                    ? "border-yellow-300 bg-gradient-to-br from-yellow-50 to-amber-100"
                    : "border-orange-300 bg-gradient-to-br from-orange-50 to-orange-100";
            const iconClass = alert.alert_level === "危険"
                ? "fa-times-circle text-red-600"
                : "fa-exclamation-triangle text-yellow-600";

            return `
                <div class="p-5 border-2 ${levelClass} rounded-2xl shadow-md hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1"
                     style="animation: slideInRight 0.4s ease-out ${index * 0.1}s both;">
                    <div class="flex items-center">
                        <div class="p-3 bg-white rounded-xl mr-4 shadow-sm">
                            <i class="fas ${iconClass} text-xl"></i>
                        </div>
                        <div class="flex-1">
                            <p class="text-sm font-bold text-gray-900">${alert.material_name}</p>
                            <p class="text-xs text-gray-600 mt-1">
                                <i class="fas fa-layer-group mr-1"></i>ロット: ${alert.lot_number}
                                <span class="mx-2">|</span>
                                <i class="fas fa-map-marker-alt mr-1"></i>${alert.location_name}
                            </p>
                        </div>
                        <div class="text-right ml-3">
                            <div class="text-lg font-black ${alert.alert_level === "危険" ? "text-red-700" : "text-yellow-700"}">
                                ${alert.current_quantity}
                            </div>
                            <div class="text-xs text-gray-600 font-semibold">本</div>
                        </div>
                    </div>
                </div>
            `;
        }).join("");
    }

    renderRecentMovements() {
        if (!this.elements.recentActivities) return;

        if (!this.state.movements.length) {
            this.elements.recentActivities.innerHTML = `
                <div class="text-center py-16">
                    <div class="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-gray-100 to-gray-200 rounded-full mb-6 shadow-inner">
                        <i class="fas fa-clock text-3xl text-gray-400"></i>
                    </div>
                    <p class="text-gray-700 font-bold text-lg">最近の入出庫はありません</p>
                    <p class="text-sm text-gray-500 mt-2">活動が記録されるとここに表示されます</p>
                </div>
            `;
            return;
        }

        this.elements.recentActivities.innerHTML = this.state.movements.map((movement, index) => {
            const isIn = movement.movement_type === "in";
            const badgeClass = isIn
                ? "bg-gradient-to-br from-green-400 to-emerald-500"
                : "bg-gradient-to-br from-red-400 to-rose-500";
            const icon = isIn ? "fa-arrow-down" : "fa-arrow-up";

            return `
                <div class="glass-card flex items-center p-5 border border-gray-200 rounded-2xl hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1"
                     style="animation: slideInLeft 0.4s ease-out ${index * 0.05}s both;">
                    <div class="p-3 ${badgeClass} rounded-xl mr-4 shadow-md">
                        <i class="fas ${icon} text-white text-lg"></i>
                    </div>
                    <div class="flex-1">
                        <p class="text-sm font-bold text-gray-900">${movement.material_name}</p>
                        <p class="text-xs text-gray-500 mt-1">
                            <i class="fas fa-layer-group mr-1"></i>${movement.lot_number}
                            <span class="mx-2">|</span>
                            <i class="fas fa-barcode mr-1"></i>${movement.item_management_code}
                        </p>
                    </div>
                    <div class="text-right ml-4">
                        <div class="text-lg font-black ${isIn ? 'text-green-700' : 'text-red-700'}">
                            ${isIn ? '+' : '-'}${Utils.formatNumber(movement.quantity)}
                        </div>
                        <div class="text-xs text-gray-600 font-semibold">
                            ${movement.weight_kg !== undefined ? `${Utils.formatNumber(movement.weight_kg, 3)} kg` : "本"}
                        </div>
                    </div>
                </div>
            `;
        }).join("");
    }

    renderForecasts() {
        if (!this.elements.stockoutForecast) return;

        if (!this.state.forecasts.length) {
            this.elements.stockoutForecast.innerHTML = `
                <div class="text-center py-12">
                    <div class="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-green-400 to-emerald-500 rounded-full mb-6 shadow-lg">
                        <i class="fas fa-clipboard-check text-3xl text-white"></i>
                    </div>
                    <p class="text-sm font-bold text-gray-800">在庫切れ予測はありません</p>
                    <p class="text-xs text-gray-500 mt-2">在庫は安定しています</p>
                </div>
            `;
            this.updateForecastSummary();
            return;
        }

        const sorted = [...this.state.forecasts]
            .filter(f => f.projected_stockout_date)
            .sort((a, b) => (a.days_until_stockout ?? 9999) - (b.days_until_stockout ?? 9999));

        const top = sorted.slice(0, 5);
        this.updateForecastSummary(top.length, top[0]?.projected_stockout_date);

        this.elements.stockoutForecast.innerHTML = top.map((forecast, index) => `
            <div class="glass-card border-2 border-purple-300 bg-gradient-to-br from-purple-50 to-fuchsia-100 rounded-2xl p-5 hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1"
                 style="animation: slideInRight 0.4s ease-out ${index * 0.1}s both;">
                <div class="flex items-center justify-between">
                    <div class="flex-1">
                        <p class="text-sm font-bold text-purple-900 mb-2">${forecast.material_spec}</p>
                        <p class="text-xs text-purple-700">
                            <i class="fas fa-boxes mr-1"></i>現庫: ${Utils.formatNumber(forecast.current_stock_bars)} 本
                        </p>
                    </div>
                    <div class="text-right ml-4">
                        <div class="text-sm font-bold text-purple-900">${forecast.projected_stockout_date ?? "-"}</div>
                        <div class="text-xs text-purple-700 font-semibold">
                            ${forecast.days_until_stockout != null ? `残り ${forecast.days_until_stockout} 日` : "未計算"}
                        </div>
                    </div>
                </div>
            </div>
        `).join("");
    }

    updateForecastSummary(count = 0, nearestDate = null) {
        if (this.elements.forecastRiskCount) {
            this.animateCounter(this.elements.forecastRiskCount, count, 1000);
        }
        if (this.elements.nearestStockout) {
            this.elements.nearestStockout.textContent = nearestDate ?? "-";
        }
    }
}

// カスタムアニメーションをCSSに追加
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes slideInLeft {
        from {
            opacity: 0;
            transform: translateX(-30px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translateX(30px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
`;
document.head.appendChild(style);

document.addEventListener("DOMContentLoaded", () => {
    if (window.APIClient && window.Utils) {
        window.dashboardPage = new DashboardPage();
    } else {
        console.error("DashboardPage: 必要な依存関係が読み込まれていません");
    }
});
