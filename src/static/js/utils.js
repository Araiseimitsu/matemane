/**
 * ユーティリティクラス
 * 共通で利用する機能を提供
 */
class Utils {
    /**
     * トースト通知表示
     */
    static showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) {
            console.warn('toast-container not found');
            return;
        }

        const toast = document.createElement('div');
        const bgColor = {
            'success': 'bg-green-500',
            'error': 'bg-red-500',
            'warning': 'bg-yellow-500',
            'info': 'bg-blue-500'
        }[type] || 'bg-blue-500';

        const icon = {
            'success': 'fas fa-check-circle',
            'error': 'fas fa-exclamation-circle',
            'warning': 'fas fa-exclamation-triangle',
            'info': 'fas fa-info-circle'
        }[type] || 'fas fa-info-circle';

        toast.className = `${bgColor} text-white px-6 py-3 rounded-lg shadow-lg transform transition-all duration-300 translate-x-full max-w-sm`;
        toast.innerHTML = `
            <div class="flex items-center">
                <i class="${icon} mr-3"></i>
                <span class="flex-1">${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-white hover:text-gray-200 focus:outline-none">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        container.appendChild(toast);

        // アニメーション（表示）
        setTimeout(() => {
            toast.classList.remove('translate-x-full');
        }, 100);

        // 自動削除（5秒後）
        setTimeout(() => {
            toast.classList.add('translate-x-full');
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.remove();
                }
            }, 300);
        }, 5000);
    }

    /**
     * 確認ダイアログ
     */
    static async confirm(message, title = '確認') {
        return new Promise((resolve) => {
            // カスタム確認ダイアログ（将来的にモーダルに置き換え可能）
            const result = confirm(`${title}\n\n${message}`);
            resolve(result);
        });
    }

    /**
     * ローディング表示/非表示
     */
    static showLoading(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.classList.remove('hidden');
        }
    }

    static hideLoading(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.classList.add('hidden');
        }
    }

    /**
     * ボタンのローディング状態を設定
     */
    static setLoading(buttonElement, isLoading) {
        if (!buttonElement) return;

        if (isLoading) {
            buttonElement.disabled = true;
            buttonElement.classList.add('opacity-50', 'cursor-not-allowed');

            // スピナーアイコンを追加
            const spinner = '<i class="fas fa-spinner fa-spin mr-2"></i>';
            const originalContent = buttonElement.innerHTML;
            buttonElement.setAttribute('data-original-content', originalContent);

            // 既存のアイコンを置き換え
            const iconMatch = originalContent.match(/<i[^>]*><\/i>/);
            if (iconMatch) {
                buttonElement.innerHTML = originalContent.replace(iconMatch[0], spinner);
            } else {
                buttonElement.innerHTML = spinner + buttonElement.textContent;
            }
        } else {
            buttonElement.disabled = false;
            buttonElement.classList.remove('opacity-50', 'cursor-not-allowed');

            // 元のコンテンツを復元
            const originalContent = buttonElement.getAttribute('data-original-content');
            if (originalContent) {
                buttonElement.innerHTML = originalContent;
                buttonElement.removeAttribute('data-original-content');
            }
        }
    }

    /**
     * フォームデータをオブジェクトに変換
     */
    static formToObject(formElement) {
        const formData = new FormData(formElement);
        const object = {};

        formData.forEach((value, key) => {
            // 複数の値がある場合（checkboxなど）
            if (object[key]) {
                if (Array.isArray(object[key])) {
                    object[key].push(value);
                } else {
                    object[key] = [object[key], value];
                }
            } else {
                object[key] = value;
            }
        });

        return object;
    }

    /**
     * 数値のフォーマット（カンマ区切り）
     */
    static formatNumber(num, decimals = 0) {
        return Number(num).toLocaleString('ja-JP', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    /**
     * 日付のフォーマット
     */
    static formatDate(dateString, includeTime = false) {
        const date = new Date(dateString);
        const options = {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        };

        if (includeTime) {
            options.hour = '2-digit';
            options.minute = '2-digit';
            options.second = '2-digit';
        }

        return date.toLocaleString('ja-JP', options);
    }

    /**
     * 材料形状の日本語名取得
     */
    static getShapeName(shape) {
        const shapeNames = {
            'round': '丸棒',
            'hexagon': '六角棒',
            'square': '角棒'
        };
        return shapeNames[shape] || shape;
    }

    /**
     * 移動タイプの日本語名取得
     */
    static getMovementTypeName(type) {
        const typeNames = {
            'receive': '入庫',
            'issue': '出庫',
            'return': '戻し',
            'move': '移動',
            'adjust': '調整'
        };
        return typeNames[type] || type;
    }

    /**
     * UUIDの短縮表示
     */
    static shortenUUID(uuid, length = 8) {
        return uuid ? uuid.substring(0, length) + '...' : '';
    }

    /**
     * クリップボードにコピー
     */
    static async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showToast('クリップボードにコピーしました', 'success');
            return true;
        } catch (error) {
            console.error('コピーエラー:', error);
            this.showToast('コピーに失敗しました', 'error');
            return false;
        }
    }

    /**
     * ファイルダウンロード
     */
    static downloadFile(blob, filename) {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }

    /**
     * 重量計算（体積 × 比重）
     */
    static calculateWeight(shape, diameterMm, lengthMm, density) {
        let volumeCm3 = 0;
        const radiusCm = (diameterMm / 2) / 10;
        const sideCm = diameterMm / 10;
        const lengthCm = lengthMm / 10;

        switch (shape) {
            case 'round':
                // 円柱の体積: π × r² × h
                volumeCm3 = Math.PI * (radiusCm ** 2) * lengthCm;
                break;
            case 'hexagon':
                // 正六角柱の体積: (3√3/2) × s² × h
                volumeCm3 = (3 * Math.sqrt(3) / 2) * (radiusCm ** 2) * lengthCm;
                break;
            case 'square':
                // 角柱の体積: s² × h
                volumeCm3 = (sideCm ** 2) * lengthCm;
                break;
            default:
                volumeCm3 = 0;
        }

        // 重量 = 体積(cm³) × 比重(g/cm³) ÷ 1000 → kg
        return (volumeCm3 * density) / 1000;
    }

    /**
     * 入力値の検証
     */
    static validateInput(value, type = 'string', options = {}) {
        switch (type) {
            case 'number':
                const num = parseFloat(value);
                if (isNaN(num)) return false;
                if (options.min !== undefined && num < options.min) return false;
                if (options.max !== undefined && num > options.max) return false;
                return true;

            case 'integer':
                const int = parseInt(value);
                if (isNaN(int) || int.toString() !== value) return false;
                if (options.min !== undefined && int < options.min) return false;
                if (options.max !== undefined && int > options.max) return false;
                return true;

            case 'string':
                if (options.required && (!value || value.trim() === '')) return false;
                if (options.minLength && value.length < options.minLength) return false;
                if (options.maxLength && value.length > options.maxLength) return false;
                return true;

            case 'uuid':
                const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
                return uuidRegex.test(value);

            case 'instruction_number':
                const instructionRegex = /^IS-\d{4}-\d{4}$/;
                return instructionRegex.test(value);

            default:
                return true;
        }
    }

    /**
     * デバウンス処理
     */
    static debounce(func, wait) {
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
     * エラーハンドリング
     */
    static handleError(error, context = '') {
        console.error(`${context} Error:`, error);

        let message = 'エラーが発生しました';
        if (error.message) {
            if (error.message.includes('401')) {
                message = '認証が必要です。ログインしてください';
                // 認証エラーの場合はログインページにリダイレクト
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
            } else if (error.message.includes('403')) {
                message = 'アクセス権限がありません';
            } else if (error.message.includes('404')) {
                message = 'データが見つかりません';
            } else if (error.message.includes('500')) {
                message = 'サーバーエラーが発生しました';
            } else {
                message = error.message;
            }
        }

        this.showToast(message, 'error');
    }

    /**
     * ローカルストレージのヘルパー
     */
    static storage = {
        set(key, value) {
            try {
                localStorage.setItem(key, JSON.stringify(value));
            } catch (error) {
                console.error('Storage set error:', error);
            }
        },

        get(key, defaultValue = null) {
            try {
                const item = localStorage.getItem(key);
                return item ? JSON.parse(item) : defaultValue;
            } catch (error) {
                console.error('Storage get error:', error);
                return defaultValue;
            }
        },

        remove(key) {
            try {
                localStorage.removeItem(key);
            } catch (error) {
                console.error('Storage remove error:', error);
            }
        }
    };

    /**
     * モーダル処理ヘルパー
     */
    static modal = {
        /**
         * モーダルを開く
         */
        open(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.remove('hidden');
                // フォーカストラップ用の最初の要素にフォーカス
                const firstInput = modal.querySelector('input, select, textarea, button');
                if (firstInput) {
                    setTimeout(() => firstInput.focus(), 100);
                }
            }
        },

        /**
         * モーダルを閉じる
         */
        close(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.add('hidden');
                // フォームがあればリセット
                const form = modal.querySelector('form');
                if (form) {
                    form.reset();
                }
            }
        },

        /**
         * 全モーダルに共通のイベントリスナーを設定
         */
        setupEventListeners(modalIds) {
            modalIds.forEach(modalId => {
                const modal = document.getElementById(modalId);
                if (!modal) return;

                // モーダル外クリックで閉じる
                modal.addEventListener('click', (e) => {
                    // モーダルコンテンツ（白い背景の要素）を探す
                    const modalContent = modal.querySelector('.bg-white');

                    // モーダルコンテンツ内のクリックかどうかをチェック
                    if (modalContent && modalContent.contains(e.target)) {
                        return; // モーダル内のクリックは無視
                    }

                    // 背景エリアのクリックならモーダルを閉じる
                    this.close(modalId);
                });

                // ESCキーで閉じる
                modal.addEventListener('keydown', (e) => {
                    if (e.key === 'Escape') {
                        e.preventDefault();
                        this.close(modalId);
                    }
                });
            });

            // グローバルESCキーイベント（どのモーダルが開いているかに関係なく）
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    // 開いているモーダルを探して閉じる
                    modalIds.forEach(modalId => {
                        const modal = document.getElementById(modalId);
                        if (modal && !modal.classList.contains('hidden')) {
                            e.preventDefault();
                            this.close(modalId);
                        }
                    });
                }
            });
        }
    };
}

// グローバルに利用可能にする
window.Utils = Utils;