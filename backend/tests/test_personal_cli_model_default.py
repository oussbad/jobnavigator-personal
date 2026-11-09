import pytest
from backend.analyzer import llm_client

@pytest.mark.parametrize('provider',['codex_cli','claude_code','antigravity_cli'])
@pytest.mark.parametrize('feature',['','scoring','autofill'])
def test_empty_cli_model_uses_cli_default_not_claude_api(monkeypatch,provider,feature):
    settings={'llm_provider':provider,'llm_model':''}
    monkeypatch.setattr(llm_client,'_get_setting',lambda db,key,default='':settings.get(key,default))
    result=llm_client.resolve_llm_config(feature,db=object())
    assert result['provider']==provider
    assert result['model']==''

def test_explicit_cli_model_is_preserved(monkeypatch):
    settings={'llm_provider':'codex_cli','llm_model':'chosen-model'}
    monkeypatch.setattr(llm_client,'_get_setting',lambda db,key,default='':settings.get(key,default))
    assert llm_client.resolve_llm_config('scoring',db=object())['model']=='chosen-model'

def test_claude_api_keeps_its_default(monkeypatch):
    monkeypatch.setattr(llm_client,'_get_setting',lambda db,key,default='':{'llm_provider':'claude_api'}.get(key,default))
    assert llm_client.resolve_llm_config('',db=object())['model']==llm_client.DEFAULT_MODEL
