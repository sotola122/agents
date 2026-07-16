# md-docs Dev Skill

md-docs は Markdown から PDF / HTML を生成する CLI パッケージです。TypeScript で実装され、Vivliostyle CLI をバックエンドに、複数の前処理スクリプトで Markdown を拡張します。

## プロジェクト構造

```
.
├── bin/md-docs.js          # CJS entry bridge → dynamic import('../lib/cli/index.js')
├── lib/cli/
│   ├── index.ts            # CLI dispatch (~150 lines)
│   ├── commands/
│   │   ├── build.ts        # Build command (main pipeline orchestrator)
│   │   ├── watch.ts        # Watch mode (chokidar-based file watcher)
│   │   ├── assets.ts       # Asset generation (watermark, theme, drawio)
│   │   ├── verify.ts       # Verification command
│   │   └── clean.ts        # Clean command
│   ├── errors.ts           # CliError class
│   └── workspace.ts        # Workspace init utilities
├── scripts/
│   ├── lib/
│   │   ├── cli.ts                     # runCliIfEntrypoint utility
│   │   ├── fs-utils.ts               # readUtf8/writeUtf8
│   │   ├── exec-utils.ts             # exec helper
│   │   ├── markdown-transforms.ts     # Pipeline transforms (270 lines)
│   │   ├── table-policy.ts           # Table splitting/policy (509 lines)
│   │   ├── build-profile-schema.ts   # Zod schema for TOML validation
│   │   ├── build-profile.cts         # CJS module: TOML+JSON config loader
│   │   └── build-profile.cts         # TS source for .cts
│   ├── preprocess-*.ts               # Build preprocessing scripts
│   ├── postbuild-*.ts                # Post-build processing
│   ├── validate-pack-payload.ts      # Publish payload validation
│   └── verify-visual.ts              # Visual regression testing
├── config/
│   ├── build-profile.toml            # Primary config (TOML)
│   └── visual-test-matrix.json       # Visual test case definitions
├── tests/
│   ├── unit/                         # Unit tests (vitest)
│   └── integration/                  # Integration tests
├── templates/base/                   # Init command seed templates
├── resources/static/                 # Static resources (logo, watermark)
├── samples/                          # Sample documents (markdown + config only)
├── package.json
├── tsconfig.json
└── vitest.config.ts
```

## TypeScript ツールチェーン

- **Runtime**: `tsx`（`.ts` ファイルを直接実行）
- **Type checking**: `tsc --noEmit`（`npm run typecheck`）
- **Module resolution**: `nodenext`（import に `.js` 拡張子が必要）
- **Target**: ES2023
- **Strict mode**: 有効
- **Import convention**: TS → TS は `.js` 拡張子（例: `import { foo } from './bar.js'`）

### 重要な設定

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2023",
    "module": "nodenext",
    "moduleResolution": "nodenext",
    "strict": true,
    "erasableSyntaxOnly": true,
    "verbatimModuleSyntax": true
  }
}
```

`erasableSyntaxOnly: true` は TypeScript 5.8+ の設定で、type-only import を強制します。
`verbatimModuleSyntax: true` により、未使用の import は自動削除されず、明示的に `type` 修飾が必要です。

### CJS との混在

- **CJS bridge**: `bin/md-docs.js`（`#!/usr/bin/env node` → `import('../lib/cli/index.js')`）
- **CJS configs**: `vivliostyle.config.cjs`、`build-profile.cts`（コンパイル後 `.cjs`）
- **理由**: Vivliostyle CLI が CJS の require() で config を読み込むため

## ビルドパイプライン

ビルドは以下の順序で直列実行されます:

1. **`preprocess-theme-tokens.ts`**: `config/build-profile.toml` から CSS カスタムプロパティ（`theme-tokens.css`）を生成
2. **`preprocess-watermark.ts`**: ウォーターマーク SVG を更新（テンプレート設定からテキストを注入）
3. **`preprocess-index.ts`**: `[include](...)` ディレクティブを展開して章ファイルを結合 → `index.assembled.md`
4. **`preprocess-wavedrom.ts`**: WaveDrom JSON → SVG 変換
5. **`preprocess-drawio.ts`**: Draw.io `.drawio` → SVG 変換（`diagramkit` ライブラリ使用）
6. **`preprocess-mermaid-gfm.ts`**: Mermaid SVG レンダリング + GitHub Alerts 変換 + 見出し番号・目次注入 + コードハイライト + 表ポリシー適用 → `index.generated.md`
7. **Vivliostyle**: `.generated.md` → PDF/HTML 出力

### 各ステージの詳細

#### preprocess-theme-tokens.ts
- `config/build-profile.toml` を読み込み
- `[fonts]`, `[template]` セクションから CSS 変数を生成
- 出力: `.tmp/generated/theme-tokens.css`

#### preprocess-watermark.ts
- 引数: `<print-css-path> <watermark-svg-path>`
- `print.css` から `@page` の `top-center` 内容を読み取り
- ウォーターマーク SVG のテキスト要素を更新
- `[template]` セクションの `watermarkText` などを反映

#### preprocess-index.ts
- 引数: `<input.md> <output.md>`
- `[include](path)` パターンを正規表現でマッチ
- インクルードされたファイルの内容をその場に展開
- ネストされたインクルードも再帰的に処理
- 最大深度制限あり（循環参照防止）

#### preprocess-wavedrom.ts
- 引数: `<json-dir> <output-image-dir>`
- `wavedrom-cli` で WaveDrom JSON → SVG 変換
- `.wavedrom` コードフェンスから JSON を抽出

#### preprocess-drawio.ts
- `diagramkit` ライブラリを使用（外部 Draw.io バイナリ不要）
- ソース: `docs/assets/resources/drawio/*.drawio`
- 出力: `docs/src/assets/resources/drawio/images/*.svg`
- 以前はシェルスクリプト + xvfb-run を使用していたが、`diagramkit` に移行済み

#### preprocess-mermaid-gfm.ts
- 複数の変換を1つのスクリプトで実行：
  - Mermaid コードフェンス → SVG（`@mermaid-js/mermaid-cli` + Puppeteer/Chromium）
  - GitHub Alerts > [!NOTE/TIP/IMPORTANT/WARNING/CAUTION] → スタイル化されたブロック
  - 見出し番号自動付与
  - 目次（TOC）生成（`## 目次` の位置に注入）
  - コードブロックのシンタックスハイライト（`shiki`）
  - 表ポリシー適用（`table-policy.ts`）
  - カバーロゴとランニングヘッダーの注入（`markdown-transforms.ts`）

### パイプラインの 2 階層構造

ビルドパイプラインは **assets.ts レベル（階層1）** と **markdown-transforms.ts レベル（階層2）** の 2 階層から構成されます。新規プリプロセススクリプトを追加する際は、どちらの階層に属するか判断する必要があります。

**階層1（assets.ts レベル）** — 独立した CLI スクリプトとして実行:
- `preprocess-theme-tokens.ts`: CSS 変数ファイルを生成
- `preprocess-watermark.ts`: SVG ウォーターマークを更新
- `preprocess-index.ts`: `[include]` を展開した `.assembled.md` を生成
- `preprocess-drawio.ts`: Draw.io ファイルを SVG 変換（`diagramkit`）
- `preprocess-wavedrom.ts`: WaveDrom JSON を SVG 変換（外部 CLI）
- `preprocess-mermaid-gfm.ts`: 最終的な Markdown 変換（階層2 を内包）

これらのスクリプトは `assets.ts` の `runAssets()` から順次呼ばれます。

**階層2（markdown-transforms.ts レベル）** — 関数として `runGeneratedMarkdownPipeline()` に統合:
- `normalizeGithubAlerts`: `> [!NOTE]` を HTML div に変換
- `processEmbedHtmlBlocks`（from `preprocess-embed-html.ts`）: ` ```html ` フェンスを raw HTML に展開
- **`processLatexBlocks`（from `preprocess-latex.ts`）**: ` ```latex ` フェンスを画像に変換（追加例）
- `applyResolvedTablePolicy`（from `table-policy.ts`）: テーブル分割・クラス付与
- `processPacketTableBlocks`（from `preprocess-packet-table.ts`）: ` ```packet-table ` を HTML テーブルに変換
- `highlightCodeBlocks`: Shiki シンタックスハイライト
- `renderMermaidBlocksToImages`: Mermaid → SVG
- `replaceMarkdownImagesWithFigures`, `numberFigureCaptions`, `injectGeneratedHeaderBlocks`, `injectTableOfContents`

これらの関数は `GENERATED_MARKDOWN_STAGE_ORDER` 配列（`markdown-transforms.ts`）で順序定義され、`runGeneratedMarkdownPipeline()` 内で直列実行されます。

**判断基準:**
- 外部バイナリ呼び出しが必要 or ファイル入出力を行う → **階層1**（assets.ts の `runAssets()` に追加）
- メモリ上の文字列変換（code fence → 別形式）→ **階層2**（`runGeneratedMarkdownPipeline()` の stage order に追加）
- ビルドプロファイルのコンテキスト（entry path, assets path）が必要 → **階層1**（`run-build-target.ts` 経由で assets.ts から呼ぶ）

### 新規コードフェンス処理追加パターン

新しい code fence 処理（例: ` ```latex ` → 画像）を追加する手順:

1. `scripts/preprocess-latex.ts` を作成し `processLatexBlocks(markdown: string): string` 関数をエクスポート
2. `scripts/lib/markdown-transforms.ts` で import: `import { processLatexBlocks } from '../preprocess-latex.js'`
3. `GENERATED_MARKDOWN_STAGE_ORDER` 配列の適切な位置に `'processLatexBlocks'` を追加
4. `runGeneratedMarkdownPipeline()` 内の該当箇所に処理を追加（`preserveCodeFences` 分岐に注意）
5. `tests/unit/preprocess-latex.test.ts` にテストを追加
6. `package.json` の `files` フィールドに `"scripts/preprocess-latex.ts"` を追加

### 重要: preprocess-mermaid-gfm.ts の特殊な起動方法

このスクリプトは `run-build-target.ts` を通して間接的に実行されます:

```bash
tsx scripts/run-build-target.ts preprocess \
  --target main \
  --script scripts/preprocess-mermaid-gfm.ts \
  --input docs/src/index.assembled.md \
  --assets docs/src/assets/mermaid \
  --inject-header \
  --inject-toc \
  --logo-source=docs/assets/logo.svg
```

これは preprocess-mermaid-gfm.ts が BUILD_PROFILE からビルドターゲット設定（entry path, assets path）を解決する必要があるためです。単純な文字列変換（packet-table, embed-html など）には `run-build-target.ts` は不要です。

### カスタム BUILD_PROFILE

ビルド時に `BUILD_PROFILE` 環境変数を設定すると、`config/build-profile.toml` 以外の設定ファイルを使用できます：

```bash
BUILD_PROFILE=samples/markdown-showcase/build-profile.toml npm run build
```

カスタムビルドでは、作業用の一時 Vivliostyle 設定ファイルが `.tmp/` に生成されます。

## CLI アーキテクチャ

### lib/cli/index.ts（CLI ディスパッチ）

- モジュール分割後、約150行に削減
- 各コマンドは `lib/cli/commands/` に個別ファイル
- コマンド名からファイルへのマッピングを持つシンプルなディスパッチ

### Build コマンド（build.ts）

- `runBuild()` がメインエントリ
- カスタム BUILD_PROFILE 処理（Vivliostyle 設定の動的生成）
- `runNodeCli()` ユーティリティを含む（subprocess 実行、stderr キャプチャ対応）

### Watch モード（watch.ts）

- `chokidar` でファイル変更を監視
- `DebouncedFunction` 型でデバウンス処理
- 監視パターンは `lib/cli/index.ts` で定義

## 設定システム

設定の優先順位（高いほど優先）:
1. `.env` 環境変数
2. `config/build-profile.toml`（Zod スキーマ検証）
3. ハードコードされたデフォルト値

### TOML サポート詳細
- **パーサー**: `smol-toml`（v1.6.1+）
- **スキーマ**: Zod（`scripts/lib/build-profile-schema.ts`、`.strict()` 使用）
- **ロード**: `scripts/lib/build-profile.cts`（CJS モジュール、Vivliostyle から require() される）
- **解決**: TOML が JSON より優先。TOML 不足項目は JSON から補完

### スキーマ（Zod）のポイント
- 全てのオブジェクトに `.strict()` を適用（未知のキーをエラーにする）
- `parseTomlConfig()`（throw）と `parseTomlConfigSafe()`（union return）の二重 API
- エラーメッセージは日本語

## テスト

このプロジェクトのテストは**3層構造**です:

| 層 | 種類 | 実行方法 | 保証範囲 |
|----|------|---------|---------|
| 1 | 単体テスト（Unit） | `npm test` / `vitest run` | 個別関数・モジュールの論理的正しさ |
| 2 | 結合テスト（Integration） | `npm test`（同） | パイプライン全体の一貫性 |
| 3 | デザインテスト（Visual Validation） | `npm run verify:visual` | 実PDFのレイアウト・フォント・画像配置の確認 |

### テストフレームワーク

- **vitest**（`^4.x`）— globals: true, coverage provider: v8
- **テストファイル配置**: `tests/**/*.test.ts`（vitest.config.ts の include 設定）
- **ヘルパー**: `tests/helpers/setup.ts`（現状空、必要に応じて setupFiles に追加）
- **fixtures**: `tests/fixtures/`（テスト用ファイル置き場、現状空）

```bash
npm test              # vitest run（全テスト実行）
npm run test:watch    # vitest（watch モード）
npm run coverage      # vitest run --coverage（カバレッジレポート）
npm run typecheck     # tsc --noEmit（テスト前に型を保証）
```

---

### 1. 単体テスト（Unit Tests）

**テスト対象**: 外部依存のない純粋関数またはモック可能な関数

#### パターンA: 純粋関数のテスト（モック不要）

入出力が明確な文字列変換関数が対象。`table-policy.ts`、`packet-table.ts`、`markdown-transforms.ts` の各変換関数が該当。

**鉄則**: 入力 Markdown の文字列を生成し、出力 HTML に期待するクラス名・タグ・テキストが含まれることを検証する。

```typescript
// tests/unit/table-policy.test.ts
import { describe, it, expect } from 'vitest';
import { applyResolvedTablePolicy, type TablePolicy } from '../../scripts/lib/table-policy.js';

const defaultPolicy: TablePolicy = {
  defaultBreakMode: 'auto',
  splitEnabled: false,
  splitRowCount: 12,
  wideColumnThreshold: 7,
  longCellThreshold: 80,
  multilineCellThreshold: 3,
  allowCommentDirectives: true,
  supportedDirectives: ['compact', 'keep-together', 'landscape', 'allow-break'],
};

it('converts pipe table to HTML when directive is present', () => {
  const input = [
    '<!-- pdf-table: compact -->',
    '| Name | Age |',
    '|------|-----|',
    '| Alice | 30 |',
    '| Bob | 25 |',
  ].join('\n');

  const result = applyResolvedTablePolicy({ markdown: input, policy: defaultPolicy });

  expect(result).toContain('<div class="table-wrapper');  // ← wrapper の存在
  expect(result).toContain('table-compact');                // ← directive クラス
  expect(result).toContain('<th>Name</th>');                // ← ヘッダー
  expect(result).toContain('<td>Alice</td>');               // ← セル内容
  expect(result).toContain('</table>');                     // ← 閉じタグ
});
```

**packet-table のテスト例**:

```typescript
it('converts a basic packet-table block to HTML', () => {
  const input = [
    '```packet-table',
    '# Ethernet Frame',
    'DestMAC: 6B',
    'SrcMAC: 6B',
    'EtherType: 2B',
    'Payload: 1500B',
    'FCS: 4B',
    '```',
  ].join('\n');

  const result = processPacketTableBlocks(input);

  expect(result).toContain('class="packet-block"');
  expect(result).toContain('class="packet-title"');
  expect(result).toContain('<span class="field-name">DestMAC</span>');
  expect(result).toContain('<span class="field-size">6B</span>');
});
```

**markdown-transforms のテスト例（GFM Alerts / TOC / ヘッダー注入）**:

```typescript
it('converts NOTE alert to HTML div', () => {
  const input = '> [!NOTE]\n> This is a note.';
  const result = normalizeGithubAlerts(input);
  expect(result).toContain('<div class="markdown-alert markdown-alert-note">');
  expect(result).toContain('<p class="markdown-alert-title">ℹ Note</p>');
  expect(result).toContain('<p>This is a note.</p>');
});

it('injects TOC before first h2 heading', () => {
  const input = 'Intro.\n\n## Section One\n\nContent.\n\n## Section Two\n\nMore content.';
  const result = injectTableOfContents(input);
  expect(result).toContain('## 目次');
  expect(result).toContain('<nav id="toc"');
  expect(result).toContain('[Section One](#section-one)');
});

it('injects running header before first h2', () => {
  const input = 'Some text.\n\n## First Heading\n\nContent.';
  const result = injectGeneratedHeaderBlocks({
    markdown: input,
    injectedLogoFileName: 'logo.png',
  });
  expect(result).toContain('id="running-header-left"');
  expect(result).toContain('Strictly Confidential');
  expect(result).toContain('id="running-header-right"');
});
```

**テスト観点の網羅ルール**:
1. **正常系**: 典型的な入力 → 期待通りの出力
2. **閾値境界**: 閾値ぴったり、閾値+1 での挙動（wideColumnThreshold, splitRowCount 等）
3. **エッジケース**: 空文字列入力、コードフェンス内の同一パターン（処理対象外の確認）
4. **通過（pass-through）**: トリガー条件を満たさない入力 → 入力がそのまま出力される
5. **エラー系**: 未対応 directive → throw されること

#### パターンB: fs モックを使用したテスト

ファイル入出力を含む関数のテスト。`preprocess-index.ts`（include 展開）が該当。

**鉄則**:
- `vi.mock('node:fs')` は **トップレベル**（describe の外）で宣言
- `mockReadUtf8.mockImplementation()` でファイルパス→内容の疑似応答を定義
- `mockWriteUtf8` の呼び出し内容を検証
- `existsSync`, `statSync` も併せてモック

```typescript
// tests/unit/preprocess-index.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockReadUtf8 = vi.fn();
const mockWriteUtf8 = vi.fn();
const mockEnsureDir = vi.fn();
const existsSync = vi.fn().mockReturnValue(true);
const statSync = vi.fn().mockReturnValue({ isFile: () => true });

vi.mock('node:fs', () => ({ existsSync, statSync }));
vi.mock('../../scripts/lib/fs-utils.js', () => ({
  readUtf8: mockReadUtf8,
  writeUtf8: mockWriteUtf8,
  ensureDir: mockEnsureDir,
}));

describe('preprocessIndex', () => {
  beforeEach(() => {
    mockReadUtf8.mockReset();
    mockWriteUtf8.mockReset();
  });

  it('expands simple include directives', async () => {
    mockReadUtf8.mockImplementation((path: string) => {
      if (path.endsWith('index.md')) return '# Main\n\n[include](./sections/chapter1.md)\n\n## End';
      if (path.endsWith('chapter1.md')) return '# Chapter 1\n\nContent.';
      throw new Error(`Unexpected path: ${path}`);
    });

    const { preprocessIndex } = await import('../../scripts/preprocess-index.js');
    preprocessIndex({
      entryMarkdown: '/root/docs/src/index.md',
      assembledMarkdown: '/root/docs/src/index.assembled.md',
    });

    const writtenContent = mockWriteUtf8.mock.calls[0][1];
    expect(writtenContent).toContain('# Chapter 1');
    expect(writtenContent).not.toContain('[include]');
  });
});
```

**テスト観点網羅**:
1. 単一インクルード展開（上記）
2. 循環インクルード検出 → `toThrow(/Circular include/i)`
3. 相対パスのリベース（`../assets/image.png` → `assets/image.png`）
4. コードフェンス内の `[include]` はスキップされること

#### パターンC: CJS モジュールのテスト

`build-profile.cts`（CJS → コンパイル後 `.cjs`）のテスト。`createRequire` で直接読み込む。

**鉄則**:
- `import` ではなく `createRequire` + `require()` を使用
- テスト内でベースプロファイルオブジェクトを構築して関数に渡す
- `vi.mock('node:fs')` は不要（CJS のモックは困難なため、純粋関数としてテスト）

```typescript
import { describe, it, expect } from 'vitest';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { getBuildTarget, resolveComposeCommand, getSampleProfile } = require('../../scripts/lib/build-profile.cjs');

it('returns main target for id "main"', () => {
  const profile = createBaseProfile();
  const result = getBuildTarget(profile, 'main');
  expect(result).toEqual({
    id: 'main',
    title: 'Test Document',
    entry: { path: 'docs/src/index.md', rel: 'contents' },
    output: 'dist/output.pdf',
    theme: ['theme-a', 'theme-b'],
  });
});

it('throws BUILD_TARGET_NOT_FOUND for unknown target id', () => {
  const profile = createBaseProfile();
  expect(() => getBuildTarget(profile, 'nonexistent'))
    .toThrow('sample profile 見つかりません: nonexistent');
});
```

#### パターンD: 動的 import + Highlighter モック

Shiki の `createHighlighter` のように非同期初期化が必要で、かつテスト環境で実際のリソースをロードできない場合。

**鉄則**:
- `beforeAll` で highlighter を非同期生成（try/catch でモックにフォールバック）
- テスト内で `await import(...)` で動的 import（モジュールが非同期初期化に依存する場合）
- モック highlighter は `codeToHtml` だけ実装すれば十分

```typescript
const createMockHighlighter = (): Highlighter =>
  ({
    codeToHtml: (code: string) =>
      `<pre class="shiki github-light"><code>${code}</code></pre>`,
  }) as unknown as Highlighter;

beforeAll(async () => {
  try {
    const { createHighlighter } = await import('shiki');
    highlighter = await createHighlighter({
      themes: ['github-light'],
      langs: ['plaintext', 'bash', 'javascript'],
    });
  } catch {
    highlighter = createMockHighlighter();
  }
});
```

### 単体テスト一覧

| ファイル | テスト数 | 対象モジュール | テストパターン |
|----------|---------|---------------|--------------|
| `tests/unit/table-policy.test.ts` | 16 | `applyResolvedTablePolicy` | A（純粋関数） |
| `tests/unit/markdown-transforms.test.ts` | 16 | `normalizeGithubAlerts`, `injectGeneratedHeaderBlocks`, `injectTableOfContents`, `numberFigureCaptions` | A（純粋関数） |
| `tests/unit/packet-table.test.ts` | 6 | `processPacketTableBlocks` | A（純粋関数） |
| `tests/unit/preprocess-index.test.ts` | 4 | `preprocessIndex` | B（fs モック） |
| `tests/unit/config-resolver.test.ts` | 11 | `getBuildTarget`, `resolveComposeCommand`, `getSampleProfile` | C（CJS require） |

### 単体テスト追加手順

1. `tests/unit/<module-name>.test.ts` を作成
2. テストパターン（A/B/C）を選択
3. 以下の観点を最低限網羅:
   - 正常系（典型的な入力）
   - 閾値境界（該当する場合）
   - エッジケース（空文字列、コードフェンス内など）
   - エラー系（該当する場合）
4. `npx vitest run tests/unit/<module-name>.test.ts` で単独実行確認
5. 全てのテストファイルを通しで実行して既存テストを壊していないことを確認

---

### 2. 結合テスト（Integration Tests）

**テスト対象**: `runGeneratedMarkdownPipeline()` — 階層2パイプライン全体

**単体テストとの違い**: 複数の変換ステージを通して、Markdown → 生成 HTML の一貫性を検証する。Shiki（シンタックスハイライト）や Mermaid（SVG レンダリング）の有無にかかわらず、パイプライン全体が例外なく動作することを確認する。

```typescript
// tests/integration/build-pipeline.test.ts
it('processes markdown through the full pipeline', async () => {
  const { runGeneratedMarkdownPipeline } = await import(
    '../../scripts/lib/markdown-transforms.js'
  );

  const result = runGeneratedMarkdownPipeline({
    markdown: makeSampleMd(),
    root: process.cwd(),
    tablePolicy: samplePolicy,
    highlighter,
    preserveGfmAlerts: false,
    preserveCodeFences: false,
    disableFigureNumbering: false,
    injectHeader: true,
    injectToc: true,
    injectedLogoFileName: 'logo.png',
    mermaidRenderOptions: {
      tempDir: '/tmp/mermaid-temp',
      mermaidOutputDir: '/tmp/mermaid-out',
      puppeteerConfig: '',
      mermaidConfig: '',
    },
  });

  // 出力が存在すること
  expect(result.content).toBeTruthy();
  expect(result.content.length).toBeGreaterThan(0);

  // 各ステージの変換結果が含まれていること
  expect(result.content).toContain('markdown-alert');           // GitHub Alerts
  expect(result.content).toContain('table-wrapper');             // 表ポリシー
  expect(result.content).toContain('table-compact');             // directive クラス
  expect(result.content).toContain('<pre');                      // コードハイライト
  expect(result.content).toContain('id="running-header-left"');  // ヘッダー注入
  expect(result.content).toContain('id="cover-logo"');           // カバーロゴ
  expect(result.content).toContain('## 目次');                  // TOC 注入
  expect(result.content).toContain('<nav id="toc"');             // TOC nav

  expect(result.figureCount).toBeTypeOf('number');
  expect(result.diagramCount).toBeTypeOf('number');
});
```

**結合テストのエッジケース**:
- **空文字列入力** → 空文字列が返り、figureCount = 0, diagramCount = 0
- **preserveGfmAlerts=true** → `> [!NOTE]` が変換されずそのまま残る
- **preserveCodeFences=true** → コードフェンスがハイライトされない

---

### 3. デザインテスト（Visual Validation）

**テスト対象**: 実 PDF のレイアウト・フォント・画像配置・ヘッダーフッター・ウォーターマーク

#### 全体構造

デザインテストは vitest とは独立したフレームワークで、`scripts/verify-visual.ts` がエントリポイントです。

```
scripts/lib/visual-validation/
├── runner.ts         # テストケースの逐次実行（ビルド→検証→レポート）
├── verifiers.ts      # ケース別検証関数（PDF テキスト抽出・画像配置判定）
├── shared.ts         # 共通ユーティリティ（PDF 解析・画像検出・ビルド実行）
└── report.ts         # Markdown レポート生成
```

テストケースは `config/visual-test-matrix.json` で定義します。

```json
{
  "version": "1",
  "globalThresholds": {
    "warnRatio": 0.01,
    "failRatio": 0.03,
    "antiAliasTolerance": 4
  },
  "cases": [
    {
      "id": "core-layout-main",
      "name": "主文書の基本レイアウト",
      "input": "docs/src/index.md",
      "buildCommand": "npm run build",
      "verifierKey": "core-layout-main",
      "generatedMarkdown": "docs/src/index.generated.md",
      "pdfOutput": "dist/basic_spec.pdf",
      "outputs": ["pdf"],
      "runtimeMatrix": ["docker", "podman"],
      "requiredChecks": [
        "japanese-fonts", "header-footer", "cover-logo",
        "header-right-logo", "images", "watermark-font",
        "main-build-axon-section"
      ],
      "manualReviewNotes": [
        "表紙下部ロゴの見え方と余白バランスは人手で最終確認",
        "表紙だけ右上ロゴが非表示になっていることを目視確認"
      ],
      "pages": [...]
    }
  ]
}
```

#### 実行方法

```bash
# 全ケース実行
npm run verify:visual

# 特定ケースのみ実行
npm run verify:visual -- --case core-layout-main

# 環境変数でケース指定・出力先変更
VISUAL_CASE=markdown-showcase-gfm npm run verify:visual
VISUAL_OUTPUT_DIR=dist/visual-check npm run verify:visual
```

**出力**:
- `dist/visual-test/report.json` — マシンリーダブルな結果
- `dist/visual-test/report.md` — 人間可読なサマリ
- `dist/visual-test/logs/` — 各ケースのビルドログ
- 終了コード: 全ケース成功=0、一つでも失敗=1

#### 検証の仕組み

各ケースには **verifier** が対応しています（`scripts/lib/visual-validation/verifiers.ts` の `verifierRegistry`）。

```
verifierRegistry = {
  'core-layout-main':     verifyCoreLayoutCase,
  'markdown-showcase-gfm': verifyShowcaseCase,
  'oversized-table-regression': verifyOversizedTableCase,
};
```

verifier が行う検証の種類:

**a. PDF テキスト抽出による確認**（`shared.ts` → `getAllPageTexts`）

pdfjs-dist で PDF の各ページからテキストを抽出し、正規表現で期待する文字列の存在を確認。

```typescript
// 表紙フッターの確認
expect(page1Text.includes('Copyright©'), '表紙にフッター文言がありません');
expect(/pg\.\s*1/.test(page1Text), '表紙にページ番号がありません');

// 日本語フォントの確認
expect(/カプセルトイ\s*業\s*界/.test(page1Text), '日本語タイトルが抽出できません');

// GitHub Alerts の確認
expect(/Note/.test(fullPdfText) && /Warning/.test(fullPdfText));

// コードブロックの確認
expect(/function\s*greet/.test(fullPdfText), 'コードブロック本文が抽出できません');

// 目次の確認
expect(/AXON\s*設計\s*書/.test(pageTexts), 'AXON 設計書見出しが抽出できません');
```

**b. 画像配置検出による確認**（`shared.ts` → `getImagePlacements`）

PDF のオペレーターリストから画像描画命令を抽出し、変換行列の位置座標からロゴの有無を判定。

```typescript
// 1ページ目の画像配置: 下部ロゴ (y > 2000)
const hasCoverLogo = page1Images.some(
  (entry) => entry.transform[4] > 900 && entry.transform[5] > 2000
);

// 1ページ目の画像配置: 右上ロゴなし (y < 500 かつ x > 1800 が存在しない)
const hasFirstPageHeaderLogo = page1Images.some(
  (entry) => entry.transform[4] > 1800 && entry.transform[5] < 500
);

// 2ページ目: 右上ロゴあり
const hasBodyHeaderLogo = page2Images.some(
  (entry) => entry.transform[4] > 1800 && entry.transform[5] < 500
);

expect(hasCoverLogo, '1ページ目に下部ロゴがありません');
expect(!hasFirstPageHeaderLogo, '1ページ目に右上ロゴがあります（非表示のはず）');
expect(hasBodyHeaderLogo, '2ページ目に右上ロゴがありません');
```

**c. 生成 Markdown の内容確認**

`generatedMarkdownPath` のファイルを読み込み、HTML 構造やクラス名の存在を確認。

```typescript
// 生成 Markdown の構造確認
expect(generatedMarkdown.includes('id="cover-logo"'));
expect(generatedMarkdown.includes('id="running-header-right"'));
expect(generatedMarkdown.includes('assets/resources/images/axon/system_design.png'));

// Shiki コードブロック数
const shikiCount = (generatedMarkdown.match(/<pre class="shiki github-light"/g) || []).length;
expect(shikiCount >= 5, `コードブロック数不足: ${shikiCount}`);

// 18.表の分割チャンク数
const markdownTableBlocks = tableBlocks.filter((block) =>
  ['<th>項目</th>', '<th>区分</th>'].every((label) => block.includes(label))
);
expect(markdownTableBlocks.length >= 4);
```

**d. 設定ファイルの整合性確認**

build-profile, theme-tokens.css, base.css, print.css などから設定値を読み取り、一致を確認。

```typescript
expect(buildProfile.fonts.body.families.includes('Noto Sans CJK JP'));
expect(themeTokens.includes('--font-family-body: "Noto Sans CJK JP"'));
expect(baseCss.includes('font-family: "IntelOneMono";'));
expect(printCss.includes('@top-right'), 'print.css に右上ヘッダー設定がありません');
```

#### 新しいデザインテストケースの追加手順

1. **サンプル文書を作成**: `samples/<new-case>/` に Markdown + `build-profile.toml` を配置
2. **visual-test-matrix.json にケースを追加**:
   - `id`: 一意の識別子（`new-feature-test`）
   - `buildCommand`: ビルドコマンド（例: `BUILD_PROFILE=samples/new-case/build-profile.toml npm run build`）
   - `verifierKey`: 対応する検証関数のキー（新規の場合は新関数を作成）
   - `requiredChecks`: 確認観点のラベル一覧
   - `manualReviewNotes`: 人手確認が必要な項目（あれば）
3. **verifier 関数を作成**: `scripts/lib/visual-validation/verifiers.ts`
   - `verifyNewFeatureCase` 関数を実装
   - 検証手段を選択: PDF テキスト抽出 / 画像配置検出 / 生成 Markdown 解析 / 設定ファイル一致確認
   - `verifierRegistry` に追加
4. **実行確認**: `npm run verify:visual -- --case new-feature-test`
5. **全ケース回帰**: `npm run verify:visual`
6. **補足**: デザインテストは実 PDF を生成するため、Chromium と Vivliostyle CLI が実行環境に必要

#### 既存のデザインテストケース一覧

| ケースID | 確認観点 | 検証手段 |
|----------|---------|---------|
| `core-layout-main` | 表紙ロゴ位置、右上ロゴ有無、日本語フォント、ヘッダーフッター、画像figure数、AXON設計書包含 | PDFテキスト抽出 + 画像配置検出 + 生成Markdown解析 + 設定ファイル一致 |
| `markdown-showcase-gfm` | GitHub Alerts 5種、Shiki コードハイライト色数、Data URI画像、IntelOneMono設定 | PDFテキスト抽出 + 生成Markdown解析 + 設定ファイル一致 |
| `oversized-table-regression` | 表分割チャンク数、ヘッダー繰り返し、改ページ位置、Markdown表/HTML表両方の分割 | 生成Markdown解析 + PDFテキスト抽出 + env設定確認 |

#### 手動確認（Manual Review）

デザインテストの一部の項目は自動判定できないため、`manualReviewNotes` としてレポートに記載されます。

```bash
# デザインテスト実行後、report.md の「手動確認メモ」セクションを確認
cat dist/visual-test/report.md

# 人手確認のためのチェックリスト
docs/design-checklist.md
```

人手で最低限確認する項目:
- 表紙下部ロゴの見え方と余白バランス
- 表紙右上ロゴが非表示であること
- ウォーターマーク文字と本文フォントの字面の混在
- 巨大表の見た目の自然さ（余白・改ページ位置）

---

### 新規コードフェンス処理追加時のテスト

新しい code fence 処理（` ```latex ` → 画像 等）を追加する場合のテスト手順:

1. **スクリプト作成**: `scripts/preprocess-latex.ts` — `processLatexBlocks(markdown: string): string` をエクスポート
2. **単体テスト**: `tests/unit/preprocess-latex.test.ts`
   - 正常系: ` ```latex ` → 画像 HTML
   - 通過: 該当しない入力 → そのまま出力
   - エッジケース: 空ブロック、コードフェンス内外
3. **パイプライン登録**: `GENERATED_MARKDOWN_STAGE_ORDER` に追加
4. **結合テスト更新**: `build-pipeline.test.ts` の `makeSampleMd()` に latex ブロックを追加し、変換後の内容を assert
5. **テスト実行**: `npm test` で全テストパス確認

### テスト実行ワークフロー

```
開発中:    npm run test:watch              # 変更検知で自動再実行
コミット前: npm run typecheck && npm test   # 型 + 全テスト
PR作成前:  npm run typecheck && npm test && npm run coverage
           npm run verify:visual -- --case core-layout-main  # 主要デザインテスト
リリース前: npm run typecheck && npm test && npm run verify:visual  # 完全検証
```

## モジュール分割パターン

### lib/cli/index.ts の分割
以前は ~850 行の単一ファイルだったが、以下に分割済み:
- `index.ts`（ディスパッチのみ、~150行）
- `commands/build.ts`（ビルド）
- `commands/watch.ts`（ウォッチ）
- `commands/assets.ts`（アセット）
- `commands/verify.ts`（検証）
- `commands/clean.ts`（クリーン）
- `errors.ts`（エラークラス）
- `workspace.ts`（ワークスペース初期化）

新規コマンド追加時は `commands/` にファイルを作成し、`index.ts` のディスパッチマップに追加します。

## 表ポリシー（table-policy.ts）

Markdown パイプ表と HTML `<table>` の両方を処理します。

### 処理内容
1. 列数が閾値以上の表に `table-wide` クラスを付与
2. 長いセルや複数行セルが閾値を超える表に `table-long` クラスを付与
3. 分割有効時は表を複数チャンクに分割
4. directive の解釈（`compact`, `keep-together`, `landscape`, `allow-break`）

### 分割動作
- Markdown 表: チャンクごとに独立した `<table>` を再生成
- HTML 表: `<tbody>` の `<tr>` をチャンク化。`<thead>` は各チャンクに残す
- 分割条件: `MARKDOWN_TABLE_SPLIT_ENABLED=true` かつ行数超過

### 設定キー
| 環境変数 / 設定 | デフォルト | 説明 |
|----------------|-----------|------|
| `MARKDOWN_TABLE_SPLIT_ENABLED` | `false` | 表分割の有効/無効 |
| `MARKDOWN_TABLE_SPLIT_ROW_COUNT` | `12` | 1チャンクあたりの行数 |
| `wideColumnThreshold` | `7` | ワイド表判定の列数閾値 |
| `longCellThreshold` | `80` | 長文セル判定の文字数閾値 |
| `multilineCellThreshold` | `3` | 複数行セル判定の行数閾値 |
| `allowCommentDirectives` | `true` | HTMLコメント directive の許可 |

## 発行（Publish）

GitHub Packages への publish は `v*.*.*` タグの push で自動実行されます。

### publish パイプラインの流れ
1. `v*.*.*` タグ push → workflow 起動
2. tag/version/scope の検証
3. Draw.io + xvfb のインストール（runner 上）
4. `bun install --frozen-lockfile`
5. `validate-pack-payload.ts` で publish payload を検証
6. `md-docs help` と `md-docs init` のスモークテスト
7. `bun publish` で GitHub Packages に公開

### publish 検証の内容
- tag と package.json の version 一致
- package scope の整合性（`@tep-hardware/md-docs`）
- publishConfig.registry の確認
- files フィールドの allowlist 確認
- `validate-pack-payload.ts` で forbidden/missing files をチェック

### package.json files 追加時の注意
新しい `.ts` ファイルを追加したら、必ず `package.json` の `files` フィールドに追加すること。追加しないと publish 時に含まれません。

## Vivliostyle 連携の注意点

- **VFM の挙動**: Vivliostyle Flavored Markdown は block-level 要素を `<h1>` 外に移動する（Markdown→HTML変換時のみ、既存HTMLには適用されない）
- **`:has()` 非対応**: Vivliostyle Crown エンジンは CSS `:has()` をサポートしない
- **`position: absolute`**: ページコンテキストで絶対配置が機能する
- **@page ルール**: `print-template.css` で `@page :first` や `@top-left` などを定義

## Draw.io → SVG 変換

- `diagramkit` ライブラリ（`^0.3.3`）を使用
- 以前のシェルスクリプト（`preprocess-drawio.sh` + xvfb-run）から移行済み
- 変換は `assets` コマンドの一部として実行
- SVG 出力パス: `docs/src/assets/resources/drawio/images/`

### 移行の背景
以前は Draw.io デスクトップアプリケーションを xvfb-run（仮想 X サーバー）経由で CLI 起動していたが、`diagramkit` により外部バイナリ依存が解消された。

## 既知の制約と注意点

- **Chromium 依存**: Mermaid レンダリングに Chromium が必要（`@mermaid-js/mermaid-cli` 経由）
- **Node 24+**: `engines.node >= 24.0.0`、`@types/node ^24.x`
- **pdfjs-dist**: Node 24 では `OffscreenCanvas` が未定義のため、NodeCanvasFactory + `canvas` パッケージが必要
- **`.tmp/` の状態敏感性**: サンプルビルド切り替え時に `.tmp/` を削除しないと stale ファイルで失敗する
- **ロゴ位置**: `#cover-logo` は `<h1>` の外側（兄弟要素）でなければ `position: absolute; bottom: 18mm` が正しく機能しない。`injectGeneratedHeaderBlocks()` の注入位置に注意