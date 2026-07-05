(() => {
    "use strict";

    /* -------------------------------------------------------
     * 1. 清除 navigator.webdriver
     * ----------------------------------------------------- */
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true
    });

    /* -------------------------------------------------------
     * 2. 删除 Chrome 自动化属性
     * ----------------------------------------------------- */
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
    delete window.__webdriver_evaluate;
    delete window.__selenium_evaluate;
    delete window.__webdriver_script_function;
    delete window.__webdriver_script_func;
    delete window.__webdriver_script_fn;
    delete window.__fxdriver_evaluate;
    delete window.__driver_unwrapped;
    delete window.__webdriver_unwrapped;
    delete window.__driver_evaluate;
    delete window.__selenium_unwrapped;
    delete window.__fxdriver_unwrapped;

    /* -------------------------------------------------------
     * 3. 清除 automation 相关属性
     * ----------------------------------------------------- */
    const cleanProps = ['_Selenium_IDE_Recorder', '_selenium', 'calledSelenium',
                       'callSelenium', '_WEBDRIVER_ELEMENTS', '_chromePromise',
                       'webdriver', 'selenium', 'driver'];
    cleanProps.forEach(prop => {
        try {
            delete window[prop];
        } catch (e) {}
    });

    /* -------------------------------------------------------
     * 4. 保存原生 Function.prototype.toString
     * ----------------------------------------------------- */
    const nativeFunctionToString = Function.prototype.toString;

    /* -------------------------------------------------------
     * 5. WeakMap：函数 → 伪原生源码
     * ----------------------------------------------------- */
    const nativeSourceMap = new WeakMap();

    /* -------------------------------------------------------
     * 6. 注册伪原生源码
     * ----------------------------------------------------- */
    const registerNativeSource = (fn, source) => {
      try {
        nativeSourceMap.set(fn, source);
      } catch (_) {}
    };

    /* -------------------------------------------------------
     * 7. 劫持 Function.prototype.toString
     * ----------------------------------------------------- */
    Object.defineProperty(Function.prototype, "toString", {
      configurable: true,
      writable: true,
      value: function toString() {
        if (nativeSourceMap.has(this)) {
          return nativeSourceMap.get(this);
        }
        return nativeFunctionToString.call(this);
      },
    });

    /* -------------------------------------------------------
     * 8. 伪装 Function.prototype.toString 自身
     * ----------------------------------------------------- */
    registerNativeSource(
      Function.prototype.toString,
      nativeFunctionToString.toString(),
    );

    /* -------------------------------------------------------
     * 9. stealthify：包装函数但保持"原生外观"
     * ----------------------------------------------------- */
    const stealthify = (obj, prop, handler) => {
      const original = obj[prop];
      if (typeof original !== "function") return;

      const wrapped = function (...args) {
        return handler.call(this, original, args);
      };
      const namePropertyDescriptor = Object.getOwnPropertyDescriptor(
        wrapped,
        "name",
      );
      Object.defineProperty(wrapped, "name", {
        ...namePropertyDescriptor,
        value: prop,
      });
      try {
        Object.setPrototypeOf(wrapped, Object.getPrototypeOf(original));
      } catch (_) {}

      registerNativeSource(wrapped, nativeFunctionToString.call(original));

      const desc = Object.getOwnPropertyDescriptor(obj, prop);
      Object.defineProperty(obj, prop, {
        ...desc,
        value: wrapped,
      });
    };

    /* -------------------------------------------------------
     * 10. 示例：stealth console
     * ----------------------------------------------------- */
    const filterConsoleArgs = (args) =>
      args.map((arg) => {
        if (arg && typeof arg === "object") {
          return {};
        }
        return arg;
      });

    ["log", "debug", "info", "warn", "error", "dir", "table"].forEach(
      (name) => {
        stealthify(console, name, (original, args) => {
          return original.apply(console, filterConsoleArgs(args));
        });
      },
    );

    /* -------------------------------------------------------
     * 11. 防御性补丁
     * ----------------------------------------------------- */
    registerNativeSource(
      registerNativeSource,
      "function registerNativeSource() { [native code] }",
    );

    /* -------------------------------------------------------
     * 12. 投递速度滑块
     * ----------------------------------------------------- */
    (function() {
        // 等待 DOM 加载完成
        function initSpeedPanel() {
            if (document.body) {
                createSpeedPanel();
            } else {
                document.addEventListener('DOMContentLoaded', createSpeedPanel);
            }
        }

        function createSpeedPanel() {
            // 避免重复创建
            if (document.getElementById('getjobs-speed-panel')) return;

            const panel = document.createElement('div');
            panel.id = 'getjobs-speed-panel';
            panel.innerHTML = `
                <div style="
                    position: fixed;
                    top: 10px;
                    right: 10px;
                    z-index: 99999;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border-radius: 12px;
                    padding: 14px 18px;
                    box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    font-size: 12px;
                    color: white;
                    min-width: 160px;
                ">
                    <div style="margin-bottom: 10px; font-weight: 600; font-size: 13px;">
                        投递速度控制
                    </div>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 11px; opacity: 0.9;">快</span>
                        <input type="range" id="delay-slider" min="0" max="3" step="0.1" value="0.2"
                            style="flex: 1; cursor: pointer; accent-color: white;">
                        <span style="font-size: 11px; opacity: 0.9;">慢</span>
                    </div>
                    <div style="text-align: center; margin-top: 8px; font-size: 14px; font-weight: 500;">
                        <span id="delay-value">0.2</span> 秒
                    </div>
                </div>
            `;
            document.body.appendChild(panel);

            const slider = panel.querySelector('#delay-slider');
            const valueDisplay = panel.querySelector('#delay-value');

            slider.addEventListener('input', function() {
                const seconds = this.value;
                valueDisplay.textContent = parseFloat(seconds).toFixed(1);
                fetch('http://127.0.0.1:8888/api/zhilian/config/delay', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({delayMs: parseFloat(seconds) * 1000})
                }).catch(function() {});
            });
        }

        initSpeedPanel();
    })();
})();
