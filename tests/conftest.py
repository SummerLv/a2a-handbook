"""
Pytest 配置和 Fixtures

此文件定义共享的 fixtures 和 pytest 配置。
"""

import pytest
import requests_mock


@pytest.fixture
def requests_mock():
    """
    requests_mock fixture 用于模拟 HTTP 响应
    
    使用示例：
        def test_something(requests_mock):
            requests_mock.get('http://example.com/api', json={'key': 'value'})
            # 现在请求会被模拟
    """
    with requests_mock.Mocker() as m:
        yield m


def pytest_configure(config):
    """
    注册自定义标记
    """
    config.addinivalue_line(
        "markers", "smoke: 核心冒烟测试，验证基本功能"
    )
    config.addinivalue_line(
        "markers", "negative: 负面测试，验证错误处理"
    )
    config.addinivalue_line(
        "markers", "slow: 慢速测试，执行时间较长"
    )
    config.addinivalue_line(
        "markers", "agent_card: Agent Card 相关测试"
    )
    config.addinivalue_line(
        "markers", "message: 消息发送相关测试"
    )
    config.addinivalue_line(
        "markers", "task: Task 生命周期测试"
    )
    config.addinivalue_line(
        "markers", "streaming: 流式响应测试"
    )
    config.addinivalue_line(
        "markers", "auth: 认证相关测试"
    )
    config.addinivalue_line(
        "markers", "boundary: 边界条件测试"
    )


def pytest_collection_modifyitems(config, items):
    """
    根据命令行选项修改测试收集
    """
    # 添加慢速测试标记
    skip_slow = pytest.mark.skip(reason="需要 --runslow 选项来运行慢速测试")
    
    if not config.getoption("--runslow", default=False):
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)


def pytest_addoption(parser):
    """
    添加自定义命令行选项
    """
    parser.addoption(
        "--runslow",
        action="store_true",
        default=False,
        help="运行慢速测试"
    )
    
    parser.addoption(
        "--base-url",
        action="store",
        default="http://localhost:8000",
        help="A2A Agent 服务的基础 URL"
    )
