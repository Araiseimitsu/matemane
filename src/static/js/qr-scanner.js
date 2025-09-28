// QRスキャナー機能

class QRScanner {
    constructor() {
        this.isScanning = false;
        this.stream = null;
        this.video = null;
        this.canvas = null;
        this.context = null;
        this.scanCallback = null;
        this.scanInterval = null;
        this.init();
    }

    init() {
        this.createVideoElement();
        this.createCanvas();
        this.bindEvents();
    }

    // ビデオ要素作成
    createVideoElement() {
        this.video = document.createElement('video');
        this.video.setAttribute('playsinline', true);
        this.video.setAttribute('autoplay', true);
        this.video.setAttribute('muted', true);
        this.video.style.cssText = `
            max-width: 100%;
            max-height: 100%;
            width: auto;
            height: auto;
            object-fit: contain;
            object-position: center;
            display: block;
            margin: 0;
            border-radius: 8px;
        `;
    }

    // キャンバス要素作成
    createCanvas() {
        this.canvas = document.createElement('canvas');
        this.context = this.canvas.getContext('2d');
    }

    // イベントバインディング
    bindEvents() {
        // QRスキャンボタン
        const scanButtons = document.querySelectorAll('[data-action="qr-scan"]');
        scanButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                this.openScanModal();
            });
        });

        // モーダル関連
        const closeScanBtn = document.getElementById('closeScanModal');
        if (closeScanBtn) {
            closeScanBtn.addEventListener('click', () => {
                this.stopScan();
            });
        }

        // QRスキャンモーダルの背景クリック時の処理
        const qrScanModal = document.getElementById('qrScanModal');
        if (qrScanModal) {
            qrScanModal.addEventListener('click', (e) => {
                if (e.target.id === 'qrScanModal') {
                    this.stopScan();
                }
            });
        }

        // ESCキーでQRスキャンモーダルを閉じる処理
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const qrModal = document.getElementById('qrScanModal');
                if (qrModal && !qrModal.classList.contains('hidden')) {
                    this.stopScan();
                }
            }
        });

        // カメラ切り替え
        const switchCameraBtn = document.getElementById('switchCameraBtn');
        if (switchCameraBtn) {
            switchCameraBtn.addEventListener('click', () => {
                this.switchCamera();
            });
        }

        // 手動入力切り替え
        const manualInputBtn = document.getElementById('manualInputBtn');
        if (manualInputBtn) {
            manualInputBtn.addEventListener('click', () => {
                this.showManualInput();
            });
        }

        // 手動入力送信
        const manualInputForm = document.getElementById('manualInputForm');
        if (manualInputForm) {
            manualInputForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.submitManualInput();
            });
        }
    }

    // QRスキャンモーダル表示
    openScanModal() {
        const modal = document.getElementById('qrScanModal');
        if (modal) {
            modal.classList.remove('hidden');
            // flex クラスは既にモーダルのHTMLに含まれているので追加不要
            this.startScan();
        }
    }

    // スキャン開始
    async startScan(callback = null) {
        if (this.isScanning) return;

        this.scanCallback = callback;
        this.isScanning = true;

        // カメラ起動中の表示を更新
        this.showCameraStarting();

        try {
            this.showToast('カメラの起動許可を待っています...', 'info');

            // カメラアクセス要求
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: 'environment', // 背面カメラを優先
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            });

            this.video.srcObject = this.stream;

            // ビデオをモーダルに追加
            const videoContainer = document.getElementById('videoContainer');
            if (videoContainer) {
                videoContainer.innerHTML = '';

                // ビデオを中央配置するためのラッパー作成
                const videoWrapper = document.createElement('div');
                videoWrapper.className = 'absolute inset-0 flex items-center justify-center bg-black';
                videoWrapper.style.cssText = `
                    width: 100%;
                    height: 100%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                `;

                // ビデオに追加のスタイル設定
                this.video.style.cssText = `
                    max-width: 100%;
                    max-height: 100%;
                    width: auto;
                    height: auto;
                    object-fit: contain;
                    object-position: center;
                    display: block;
                    margin: 0;
                    border-radius: 8px;
                `;

                videoWrapper.appendChild(this.video);
                videoContainer.appendChild(videoWrapper);

                // カメラ起動中の表示を追加
                this.addCameraStatusIndicator();
            }

            await this.video.play();

            // カメラ起動完了の表示
            this.showCameraActive();

            // スキャン開始
            this.scanInterval = setInterval(() => {
                this.scanFrame();
            }, 100);

            this.showToast('カメラが起動しました。QRコードをカメラに向けてください', 'success');

        } catch (error) {
            console.error('Camera access error:', error);

            if (error.name === 'NotAllowedError') {
                this.showToast('カメラの許可が拒否されました。ブラウザの設定でカメラアクセスを許可してください', 'error');
            } else if (error.name === 'NotFoundError') {
                this.showToast('カメラが見つかりません。デバイスにカメラが接続されているか確認してください', 'error');
            } else {
                this.showToast('カメラにアクセスできません。手動入力をご利用ください', 'error');
            }

            this.showManualInput();
        }
    }

    // カメラ起動中表示
    showCameraStarting() {
        const videoContainer = document.getElementById('videoContainer');
        if (videoContainer) {
            videoContainer.innerHTML = `
                <div class="absolute inset-0 flex items-center justify-center text-white bg-gray-800">
                    <div class="text-center">
                        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
                        <p class="text-lg font-medium">カメラを起動中...</p>
                        <p class="text-sm mt-2 text-gray-300">カメラアクセスの許可を求めています</p>
                    </div>
                </div>
            `;
        }
    }

    // カメラステータスインジケーター追加
    addCameraStatusIndicator() {
        const videoContainer = document.getElementById('videoContainer');
        if (videoContainer) {
            const indicator = document.createElement('div');
            indicator.id = 'cameraStatusIndicator';
            indicator.className = 'absolute top-4 left-4 z-10';
            videoContainer.appendChild(indicator);
        }
    }

    // カメラアクティブ表示
    showCameraActive() {
        const indicator = document.getElementById('cameraStatusIndicator');
        if (indicator) {
            indicator.innerHTML = `
                <div class="flex items-center bg-green-600 text-white px-3 py-2 rounded-lg shadow-lg">
                    <div class="w-3 h-3 bg-green-300 rounded-full mr-2 animate-pulse"></div>
                    <span class="text-sm font-medium">カメラ起動中</span>
                </div>
            `;
        }

        // QRコードフレーム表示
        this.showQRFrame();
    }

    // QRコードフレーム表示
    showQRFrame() {
        const videoContainer = document.getElementById('videoContainer');
        if (videoContainer) {
            const frame = document.createElement('div');
            frame.className = 'absolute inset-0 pointer-events-none';
            frame.innerHTML = `
                <div class="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-64 h-64 border-4 border-white rounded-lg">
                    <div class="absolute top-0 left-0 w-8 h-8 border-t-4 border-l-4 border-green-400 rounded-tl-lg"></div>
                    <div class="absolute top-0 right-0 w-8 h-8 border-t-4 border-r-4 border-green-400 rounded-tr-lg"></div>
                    <div class="absolute bottom-0 left-0 w-8 h-8 border-b-4 border-l-4 border-green-400 rounded-bl-lg"></div>
                    <div class="absolute bottom-0 right-0 w-8 h-8 border-b-4 border-r-4 border-green-400 rounded-br-lg"></div>
                    <div class="absolute inset-0 flex items-center justify-center">
                        <p class="text-white bg-black bg-opacity-50 px-3 py-1 rounded text-sm">QRコードをここに合わせてください</p>
                    </div>
                </div>
            `;
            videoContainer.appendChild(frame);
        }
    }

    // フレームスキャン
    scanFrame() {
        if (!this.isScanning || !this.video.videoWidth || !this.video.videoHeight) {
            return;
        }

        // キャンバスサイズ設定
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;

        // ビデオフレームをキャンバスに描画
        this.context.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

        // 画像データ取得
        const imageData = this.context.getImageData(0, 0, this.canvas.width, this.canvas.height);

        // QRコード検出（jsQRライブラリ使用を想定）
        if (window.jsQR) {
            const code = jsQR(imageData.data, imageData.width, imageData.height);

            if (code) {
                this.onQRCodeDetected(code.data);
            }
        } else {
            // jsQRライブラリがない場合の代替処理
            this.detectQRCodeFallback(imageData);
        }
    }

    // QRコード検出フォールバック
    detectQRCodeFallback(imageData) {
        // 簡易的な検出処理（実際の運用では外部ライブラリを推奨）
        // ここでは定期的に手動入力を促すメッセージを表示
        if (Math.random() < 0.01) { // 1%の確率で表示
            this.showToast('QRコードが検出されない場合は手動入力をご利用ください', 'info');
        }
    }

    // QRコード検出時の処理
    onQRCodeDetected(qrData) {
        this.showToast('QRコードを検出しました！', 'success');
        this.stopScan();

        // コールバック実行
        if (this.scanCallback) {
            this.scanCallback(qrData);
        } else {
            // デフォルト処理：管理コード検索
            this.searchByQRCode(qrData);
        }
    }

    // QRコードでの検索処理
    searchByQRCode(qrData) {
        // 各画面に応じた処理を実行
        if (window.inventoryManager) {
            window.inventoryManager.searchByCode(qrData);
        } else if (window.movementManager) {
            const codeInput = document.getElementById('managementCodeInput');
            if (codeInput) {
                codeInput.value = qrData;
            }
            window.movementManager.searchByCode();
        } else {
            // デフォルト：在庫検索ページに遷移
            window.location.href = `/inventory?search=${encodeURIComponent(qrData)}`;
        }
    }

    // カメラ切り替え
    async switchCamera() {
        if (!this.isScanning) return;

        try {
            // 現在のストリーム停止
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
            }

            // フロントカメラとバックカメラを切り替え
            const currentFacingMode = this.getCurrentFacingMode();
            const newFacingMode = currentFacingMode === 'environment' ? 'user' : 'environment';

            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: newFacingMode,
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            });

            this.video.srcObject = this.stream;
            await this.video.play();

            this.showToast('カメラを切り替えました', 'success');

        } catch (error) {
            console.error('Camera switch error:', error);
            this.showToast('カメラの切り替えに失敗しました', 'error');
        }
    }

    // 現在のカメラ向き取得
    getCurrentFacingMode() {
        if (!this.stream) return 'environment';

        const videoTrack = this.stream.getVideoTracks()[0];
        const settings = videoTrack.getSettings();
        return settings.facingMode || 'environment';
    }

    // 手動入力表示
    showManualInput() {
        const manualInputDiv = document.getElementById('manualInputDiv');
        const videoContainer = document.getElementById('videoContainer');

        if (manualInputDiv && videoContainer) {
            videoContainer.classList.add('hidden');
            manualInputDiv.classList.remove('hidden');
        }

        // スキャン停止
        this.pauseScan();
    }

    // スキャン一時停止
    pauseScan() {
        if (this.scanInterval) {
            clearInterval(this.scanInterval);
            this.scanInterval = null;
        }
    }

    // 手動入力送信
    submitManualInput() {
        const input = document.getElementById('manualCodeInput');
        const code = input?.value?.trim();

        if (!code) {
            this.showToast('コードを入力してください', 'error');
            return;
        }

        this.onQRCodeDetected(code);
    }

    // スキャン停止
    stopScan() {
        this.isScanning = false;

        // スキャン間隔停止
        if (this.scanInterval) {
            clearInterval(this.scanInterval);
            this.scanInterval = null;
        }

        // ストリーム停止
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }

        // ビデオ停止
        if (this.video) {
            this.video.srcObject = null;
        }

        // モーダル非表示
        const modal = document.getElementById('qrScanModal');
        if (modal) {
            modal.classList.add('hidden');
        }

        // 手動入力をリセット
        this.resetManualInput();
    }

    // 手動入力リセット
    resetManualInput() {
        const manualInputDiv = document.getElementById('manualInputDiv');
        const videoContainer = document.getElementById('videoContainer');
        const manualInput = document.getElementById('manualCodeInput');

        if (manualInputDiv && videoContainer) {
            manualInputDiv.classList.add('hidden');
            videoContainer.classList.remove('hidden');
        }

        if (manualInput) {
            manualInput.value = '';
        }
    }

    // 外部から呼び出し用
    startScanWithCallback(callback) {
        this.scanCallback = callback;
        this.openScanModal();
    }

    // カメラサポート確認
    static isSupported() {
        return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    }

    // トースト通知
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        const bgColor = {
            'success': 'bg-green-500',
            'error': 'bg-red-500',
            'warning': 'bg-yellow-500',
            'info': 'bg-blue-500'
        }[type] || 'bg-blue-500';

        toast.className = `fixed top-4 right-4 ${bgColor} text-white px-6 py-3 rounded-lg shadow-lg z-50 transform transition-transform duration-300 translate-x-full`;
        toast.textContent = message;

        document.body.appendChild(toast);

        // アニメーション
        setTimeout(() => {
            toast.classList.remove('translate-x-full');
        }, 100);

        // 自動削除
        setTimeout(() => {
            toast.classList.add('translate-x-full');
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 3000);
    }
}

// QRスキャンモーダルHTML生成
function createQRScanModal() {
    const modalHTML = `
        <div id="qrScanModal" class="fixed inset-0 bg-gray-600 bg-opacity-50 hidden z-50 flex items-center justify-center">
            <div class="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[95vh] overflow-y-auto mx-4">
                <div class="px-6 py-4 border-b border-gray-200">
                    <div class="flex justify-between items-center">
                        <h3 class="text-lg font-semibold text-gray-900">QRコードスキャン</h3>
                        <button id="closeScanModal" type="button" class="text-gray-400 hover:text-gray-600">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>
                </div>

                <div class="p-6">
                    <!-- ビデオ表示エリア -->
                    <div id="videoContainer" class="relative bg-black rounded-lg overflow-hidden mb-4 w-full" style="aspect-ratio: 4/3; min-height: 320px;">
                        <!-- ビデオ要素はJavaScriptで挿入 -->
                        <div class="absolute inset-0 flex items-center justify-center text-white">
                            <div class="text-center">
                                <svg class="mx-auto h-12 w-12 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"></path>
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"></path>
                                </svg>
                                <p>カメラを起動中...</p>
                            </div>
                        </div>
                    </div>

                    <!-- 手動入力エリア -->
                    <div id="manualInputDiv" class="hidden">
                        <form id="manualInputForm" class="space-y-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-2">管理コード</label>
                                <input type="text" id="manualCodeInput" required
                                       class="w-full px-4 py-2.5 border border-gray-300 rounded-lg bg-white text-gray-900 placeholder-gray-500 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                       placeholder="管理コードを入力してください">
                            </div>
                            <button type="submit"
                                    class="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 px-6 rounded-lg transition-all duration-200">
                                検索
                            </button>
                        </form>
                    </div>

                    <!-- 操作ボタン -->
                    <div class="flex space-x-3">
                        <button id="switchCameraBtn" type="button"
                                class="flex-1 bg-gray-100 text-gray-700 font-medium py-2.5 px-4 rounded-lg transition-all duration-200 hover:bg-gray-200">
                            <svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path>
                            </svg>
                            切替
                        </button>
                        <button id="manualInputBtn" type="button"
                                class="flex-1 bg-blue-100 text-blue-700 font-medium py-2.5 px-4 rounded-lg transition-all duration-200 hover:bg-blue-200">
                            <svg class="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                            </svg>
                            手動入力
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // モーダルをbodyに追加
    document.body.insertAdjacentHTML('beforeend', modalHTML);
}

// グローバル変数として初期化
let qrScanner;

// DOM読み込み完了後に初期化
document.addEventListener('DOMContentLoaded', () => {
    // QRスキャンモーダル作成
    createQRScanModal();

    // QRスキャナー初期化
    if (QRScanner.isSupported()) {
        qrScanner = new QRScanner();
        window.qrScanner = qrScanner; // グローバルアクセス用
    } else {
        console.warn('QRスキャナーはこのブラウザではサポートされていません');
    }
});