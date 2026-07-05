# Snipaste OCR 辅助脚本
# 使用方法：PowerShell 启动后，在后台运行
# 按 Win+O 对剪贴板图片进行 OCR

Add-Type -AssemblyName System.Runtime.WindowsRuntime
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Storage.FileAccessMode, Windows.Storage, ContentType = WindowsRuntime]

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()

Write-Host "Snipaste OCR 辅助脚本已启动"
Write-Host "使用: 截图后按 Ctrl+C，然后按 Win+O"
Write-Host "按 Ctrl+C 退出..."

# 注册全局热键 Win+O
# 使用 .NET 的 RegisterHotKey
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;

public class GlobalHotkey {
    [DllImport("user32.dll")]
    public static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

    [DllImport("user32.dll")]
    public static extern bool UnregisterHotKey(IntPtr hWnd, int id);

    public const uint MOD_WIN = 0x0008;
    public const uint VK_O = 0x4F;
}
"@

$form = New-Object System.Windows.Forms.Form
$form.Text = "Snipaste OCR"
$form.ShowInTaskbar = $false
$form.WindowState = [System.Windows.Forms.FormWindowState]::Minimized

$form.Add_Shown({
    $null = [GlobalHotkey]::RegisterHotKey($form.Handle, 1, [GlobalHotkey]::MOD_WIN, [GlobalHotkey]::VK_O)
    Write-Host "[$PID] 热键 Win+O 已注册"
})

$form.Add_KeyDown({
    param($sender, $e)
    if ($e.KeyCode -eq [System.Windows.Forms.Keys]::O -and $e.Modifiers -eq [System.Windows.Forms.Keys]::Win) {
        Write-Host "[OCR] 检测到 Win+O，开始处理..."
        $text = ""

        try {
            if ([System.Windows.Forms.Clipboard]::ContainsImage()) {
                $img = [System.Windows.Forms.Clipboard]::GetImage()
                $ms = New-Object System.IO.MemoryStream
                $img.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
                $bytes = $ms.ToArray()
                $ms.Close()

                $tempFile = "$env:TEMP\ocr_temp_$(Get-Random).png"
                [System.IO.File]::WriteAllBytes($tempFile, $bytes)

                $file = [Windows.Storage.StorageFile]::GetFileFromPathAsync($tempFile).GetAwaiter().GetResult()
                $stream = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read).GetAwaiter().GetResult()
                $decoder = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream).GetAwaiter().GetResult()
                $softwareBitmap = $decoder.GetSoftwareBitmapAsync().GetAwaiter().GetResult()
                $ocrResult = $engine.RecognizeAsync($softwareBitmap).GetAwaiter().GetResult()
                $text = $ocrResult.Text

                Remove-Item $tempFile -Force -ErrorAction SilentlyContinue

                if ($text -and $text.Trim().Length -gt 0) {
                    [System.Windows.Forms.Clipboard]::SetText($text)
                    Write-Host "[OCR] 成功！内容已复制到剪贴板："
                    Write-Host "---"
                    Write-Host $text
                    Write-Host "---"
                } else {
                    Write-Host "[OCR] 未识别到文字"
                }
            } else {
                Write-Host "[OCR] 剪贴板无图片，请先截图并 Ctrl+C"
            }
        } catch {
            Write-Host "[OCR] 错误: $($_.Exception.Message)"
        }
    }
})

$form.Add_FormClosing({
    [GlobalHotkey]::UnregisterHotKey($form.Handle, 1) | Out-Null
})

[System.Windows.Forms.Application]::Run($form)
