"""experiments/09_drone_hover_rl/politica.py — ator-crítico ASSIMÉTRICO para o drone real (plano §7 D1).

O ATOR (o que vai para o RPi 5) só pode usar a parte REAL da observação — `obs[:n_ator]` (sensores +
estimação de bordo + ação anterior). O CRÍTICO (só existe no treino) vê tudo, incluindo a informação
privilegiada `obs[n_ator:]` (posição/velocidade/atitude exatas, SoC, vento): é o "asymmetric actor-critic"
padrão de sim-to-real — valor mais preciso, política que não depende do que não existe no hardware.

Mecanismo no SB3 2.9 (`ActorCriticPolicy`, extratores NÃO partilhados): o 1.º extrator criado é o do ator
e MULTIPLICA a observação por uma máscara [1…1, 0…0] (as entradas privilegiadas chegam a zero, logo os
pesos correspondentes não recebem gradiente e o `weight_decay` leva-os a 0); o 2.º é o do crítico
(identidade). O `deploy.py` exporta o ator com entrada `(1, n_ator)` e preenche o resto com zeros.
"""
from __future__ import annotations

import gymnasium as gym
import torch as th
from stable_baselines3.common.policies import ActorCriticPolicy
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor, FlattenExtractor


class ExtratorAtor(BaseFeaturesExtractor):
    """Mantém só as `n_ator` primeiras entradas (as restantes ficam a 0) — mesma dimensão de saída."""

    def __init__(self, observation_space: gym.spaces.Box, n_ator: int):
        dim = int(observation_space.shape[0])
        super().__init__(observation_space, features_dim=dim)
        mascara = th.zeros(dim)
        mascara[: int(n_ator)] = 1.0
        self.register_buffer("mascara", mascara)
        self.n_ator = int(n_ator)

    def forward(self, observations: th.Tensor) -> th.Tensor:
        return observations.flatten(1) * self.mascara


class PoliticaAssimetrica(ActorCriticPolicy):
    """`ActorCriticPolicy` com o ator restrito a `obs[:n_ator]` e o crítico com a observação completa."""

    def __init__(self, *args, n_ator: int, **kwargs):
        self._n_ator = int(n_ator)
        self._n_extratores = 0
        kwargs["share_features_extractor"] = False
        super().__init__(*args, **kwargs)

    def make_features_extractor(self) -> BaseFeaturesExtractor:
        self._n_extratores += 1
        if self._n_extratores == 1:                 # o 1.º é o do ATOR (features_extractor/pi)
            return ExtratorAtor(self.observation_space, self._n_ator)
        return FlattenExtractor(self.observation_space)   # o 2.º é o do CRÍTICO (vf)

    def _get_constructor_parameters(self) -> dict:
        dados = super()._get_constructor_parameters()
        dados["n_ator"] = self._n_ator
        return dados

    def acao_ator(self, obs_ator: th.Tensor) -> th.Tensor:
        """Média da ação a partir SÓ da parte real da observação (o grafo que vai para o ONNX)."""
        n_total = int(self.observation_space.shape[0])
        completa = th.zeros((obs_ator.shape[0], n_total), dtype=obs_ator.dtype, device=obs_ator.device)
        completa[:, : self._n_ator] = obs_ator
        feats = self.pi_features_extractor(completa)
        return self.action_net(self.mlp_extractor.forward_actor(feats))
