"""Real Qt regression coverage for streaming bubble geometry (#21)."""

import math

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop_client.gui.markdown_utils import MarkdownLabel


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def settle(qt_app):
    QTest.qWait(40)
    qt_app.processEvents()


def assert_content_fits(label):
    assert label.document().size().width() <= label.viewport().width() + 1
    assert math.ceil(label.document().size().height()) <= label.viewport().height()
    assert label.horizontalScrollBar().maximum() == 0
    assert label.verticalScrollBar().maximum() == 0


def test_streaming_bubble_grows_after_short_first_chunk(qt_app):
    label = MarkdownLabel("Hi")
    label.setMaximumWidth(300)
    label.show()
    try:
        settle(qt_app)
        initial_width = label.width()
        for text in ["Hi, this reply grows with every token. " * 5,
                     "中文流式回复，持续增长并自动换行。" * 80]:
            label.set_markdown(text)
            settle(qt_app)
            print(f"initial={initial_width}, current={label.width()}, "
                  f"document={label.document().size()}, viewport={label.viewport().size()}")
            assert initial_width < label.width() <= 300
            assert_content_fits(label)
    finally:
        label.close()
        label.deleteLater()
        qt_app.processEvents()


@pytest.mark.parametrize("text", [
    "", "a", "中文🙂 " * 300, "word " * 2000, "x" * 500,
    "# 标题\n\n- 第一条\n- **第二条**\n\n> 引用\n\n" * 20,
    "```python\nprint('hello')\n```\n" * 20,
    "| a | b |\n|---|---|\n| cell | value |\n",
], ids=["empty", "single", "unicode", "long-prose", "unbroken-word", "rich-text", "code", "table"])
def test_markdown_size_and_theme_updates(qt_app, text):
    label = MarkdownLabel("x")
    label.setMaximumWidth(220)
    label.show()
    try:
        settle(qt_app)
        label.set_markdown(text)
        settle(qt_app)
        assert 1 <= label.width() <= 220
        assert_content_fits(label)
        label.update_theme()
        settle(qt_app)
        assert_content_fits(label)
        label.set_markdown("ok")
        settle(qt_app)
        assert label.width() < 100
    finally:
        label.close()
        label.deleteLater()
        qt_app.processEvents()
