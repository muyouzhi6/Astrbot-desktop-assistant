"""
支持 python -m desktop_client 方式运行
"""
import sys
import warnings

# ============================================================
# 抑制 httpcore 异步生成器清理警告
# 这是 httpcore/httpx 与 asyncio 结合使用时的已知问题
# https://github.com/encode/httpx/issues/2171
# ============================================================

# 抑制 warnings 模块的警告
warnings.filterwarnings("ignore", message="async generator ignored GeneratorExit")
warnings.filterwarnings("ignore", message="Attempted to exit cancel scope")

# 自定义异常钩子来过滤 httpcore 的 async generator 清理异常
_original_excepthook = sys.excepthook


def _custom_excepthook(exc_type, exc_value, exc_tb):
    """自定义异常钩子，过滤 httpcore 相关的异常"""
    # 检查是否是 httpcore async generator 清理异常
    if exc_type is RuntimeError:
        msg = str(exc_value)
        if "async generator ignored GeneratorExit" in msg:
            return  # 静默忽略
        if "Attempted to exit cancel scope" in msg:
            return  # 静默忽略
    
    # 其他异常正常处理
    _original_excepthook(exc_type, exc_value, exc_tb)


sys.excepthook = _custom_excepthook

# 同时处理 unraisable exceptions (Python 3.8+)
if hasattr(sys, 'unraisablehook'):
    _original_unraisablehook = sys.unraisablehook
    
    def _custom_unraisablehook(unraisable):
        """自定义 unraisable 异常钩子"""
        exc_type = unraisable.exc_type
        exc_value = unraisable.exc_value
        
        # 检查是否是 httpcore async generator 清理异常
        if exc_type is RuntimeError:
            msg = str(exc_value) if exc_value else ""
            if "async generator ignored GeneratorExit" in msg:
                return  # 静默忽略
            if "Attempted to exit cancel scope" in msg:
                return  # 静默忽略
        
        # 检查对象名称是否包含 httpcore
        obj = unraisable.object
        if obj is not None:
            obj_repr = repr(obj)
            if "HTTP11ConnectionByteStream" in obj_repr:
                return  # 静默忽略 httpcore 流相关异常
        
        # 其他异常正常处理
        _original_unraisablehook(unraisable)
    
    sys.unraisablehook = _custom_unraisablehook

# ============================================================

print("[DEBUG] 正在加载模块...")

try:
    print("[DEBUG] 导入 app 模块...")
    from .app import main
    print("[DEBUG] 模块导入成功")
except ImportError as e:
    print(f"[ERROR] 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    print("[DEBUG] 启动主函数...")
    main()