from gymnasium.envs.registration import register

register(
     id="ransim/SinarioOne-v0",
     entry_point="ransim_mp_env.envs.sinario_one:SinarioOne",
)

register(
     id="ransim/SinarioTwo-v0",
     entry_point="ransim_env.envs.sinario_two:SinarioTwo",
)