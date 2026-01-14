# デザインルール - サービスチェッカー

ダークグリーンベースのミニマルな監視UI。視認性の高いアクセントカラーとバッジ形式のステータス表示が特徴。

## カラーパレット

### ベースカラー

| 用途 | CSS変数 | 値 |
|------|---------|-----|
| 背景 (最も暗い) | `--color-base` | `#1E2613` |
| サーフェス | `--color-surface` | `#262E1D` |
| サーフェス (明るい) | `--color-surface-light` | `#333D2C` |
| メインアクセント | `--color-main` | `#C4D6B3` |
| セカンダリアクセント | `--color-accent` | `#FFD97D` |
| テキスト | `--color-text` | `#E0E0E0` |
| ミュートテキスト | `--color-muted` | `#808080` |

### ステータスカラー

| ステータス | CSS変数 | 値 |
|------------|---------|-----|
| 到達可能 | `--color-reachable` | `#2D8A5E` |
| 到達不可 | `--color-unreachable` | `#A31D1D` |
| 不明 | `--color-unknown` | `#555555` |
| プライベート | `--color-private` | `#3A72F5` |
| Tailscale | `--color-tailscale` | `#31589C` |

## タイポグラフィ

```css
font-family: 'Segoe UI', system-ui, sans-serif;
```

### フォントサイズ

| 用途 | サイズ |
|------|--------|
| ベース | `14px` |
| h1 | `1.5em` |
| メタ情報 | `0.85em` |
| ラベル | `0.75em` |
| テーブルヘッダー | `0.8em` |
| 小さいテキスト | `0.8em` |

### 等幅フォント (IP・ポート表示用)

```css
font-family: 'Consolas', monospace;
```

## レイアウト

| プロパティ | 値 |
|------------|-----|
| 最大幅 | `1400px` |
| 基本padding | `16px` |
| border-radius | `6px` (`--border-radius`) |
| トランジション | `0.2s ease` (`--transition`) |

## コンポーネント

### ボタン

#### 基本スタイル

```css
.btn {
    padding: 6px 12px;
    border: none;
    border-radius: var(--border-radius);
    font-weight: 600;
    font-size: 0.85em;
}
```

#### バリエーション

| クラス | 背景色 | 文字色 | 用途 |
|--------|--------|--------|------|
| `.btn-primary` | `--color-accent` (#FFD97D) | `--color-base` | 登録・保存 |
| `.btn-success` | `--color-reachable` (#2D8A5E) | white | チェック実行 |
| `.btn-danger` | `--color-unreachable` (#A31D1D) | white | 削除 |
| `.btn-secondary` | `--color-surface-light` (#333D2C) | `--color-text` | キャンセル・検索 |
| `.btn-sm` | - | - | padding: 4px 8px, font-size: 0.8em |

### ステータスバッジ

```css
.status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 20px;  /* 丸みを帯びたピル型 */
    font-size: 0.85em;
    font-weight: 600;
}
```

| ステータス | クラス | 背景色 | 表示テキスト |
|------------|--------|--------|--------------|
| 到達可能 | `.status.reachable` | `#2D8A5E` | OK + レイテンシ |
| 到達不可 | `.status.unreachable` | `#A31D1D` | NG |
| 不明 | `.status.unknown` | `#555555` | ? |
| チェック中 | `.status.checking` | `#FFD97D` | チェック中... (アニメーション付き) |

### フォーム

#### 入力フィールド

```css
input {
    padding: 8px;
    border: 1px solid var(--color-surface-light);
    background: var(--color-base);
    color: var(--color-text);
    border-radius: var(--border-radius);
}
```

#### ラベル

```css
label {
    font-size: 0.75em;
    color: var(--color-main);
    font-weight: 600;
}
```

### テーブル

```css
table {
    width: 100%;
    border-collapse: collapse;
    background: var(--color-surface);
    border-radius: var(--border-radius);
    overflow: hidden;
}

th {
    background: var(--color-surface-light);
    font-size: 0.8em;
    font-weight: 600;
    color: var(--color-main);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

th, td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--color-base);
}

tr:hover {
    background: rgba(255, 255, 255, 0.03);
}
```

### ヘッダー

```css
.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--color-surface-light);
}

.header h1 {
    font-size: 1.5em;
    color: var(--color-main);
}

.header-meta {
    font-size: 0.85em;
    color: var(--color-muted);
}
```

### グループヘッダー

```css
.group-header {
    background: var(--color-surface-light);
    padding: 10px 14px;
    border-radius: var(--border-radius);
}

.group-name {
    font-weight: 700;
    color: var(--color-main);
}

.group-stats {
    font-size: 0.85em;
    color: var(--color-muted);
}
```

### チェックボタン (丸型)

```css
.check-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-surface-light);
    border: none;
    border-radius: 50%;
    cursor: pointer;
    color: var(--color-text);
}

.check-btn:hover {
    background: var(--color-reachable);
    color: white;
}
```

### お気に入りボタン

```css
.favorite-btn {
    background: none;
    border: none;
    font-size: 1.2em;
    color: var(--color-muted);
}

.favorite-btn.active {
    color: var(--color-accent);
}
```

### フラッシュメッセージ

| カテゴリ | 背景色 |
|----------|--------|
| success | `--color-reachable` (#2D8A5E) |
| error | `--color-unreachable` (#A31D1D) |
| info | `--color-private` (#3A72F5) |
| warning | `#B8860B` |

## アニメーション

### パルス (チェック中)

```css
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}
```

### スピン (チェックボタン回転)

```css
@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}
```

## 使用アイコン

SVGアイコンを使用（ストローク幅: 2px）

- **更新/リフレッシュ**: 2つの矢印が循環するアイコン

## 注意事項

- `base.html` には別の（古い）ライトテーマのスタイルが残っているが、`index.html` では独自のダークテーマを使用
- 将来的には `base.html` のスタイルも統一することを推奨
