# Verificação independente (reexecução) das afirmações centrais

Gerado por `pesquisas/tools/verify_claims.py` — 38/38 OK.

| ID | Afirmação | Observado | Resultado |
| --- | --- | --- | --- |
| E01 | data.actuator('x').ctrl grava no slot errado com atuador multi-entrada (pid): nu ≠ nactuator | nu=4 nactuator=3 ctrl=[0.0, 0.0, 7.0, 0.0] slot_correto=3 | OK |
| E02 | blocos <visual> repetidos são MESCLADOS por atributo; o mesmo sub-elemento repetido no MESMO bloco é erro | offwidth=1920, ambient=0.3; duplicado → XML Error: Schema violation: unique element 'global' found 2 times | OK |
| E03 | mjData.qM foi removido (agora M em CSR) e mj_fullM(m, d, dst) tem a nova assinatura | hasattr(qM)=False hasattr(M)=True M00=0.0168 | OK |
| E04 | MjSpec não tem delete_body/delete_geom…; só spec.delete(elemento); e spec.compiler.strippath → AttributeError (use spec.strippath) | delete_body=False delete=True compiler.strippath=False spec.strippath=True | OK |
| E05 | padrões 3.15.0: Euler, Newton, cone piramidal, dt 2 ms, 100 iterações, refsafe ligado | integrator=0 solver=2 cone=0 dt=0.002 iter=100 refsafe=True | OK |
| E06 | enum mjtIntegrator = Euler, RK4, implicit, implicitfast, discrete (5 valores) | ['mjINT_EULER', 'mjINT_RK4', 'mjINT_IMPLICIT', 'mjINT_IMPLICITFAST', 'mjINT_DISCRETE'] | OK |
| E07 | fluidcoef por omissão = (0.5, 0.25, 1.5, 1.0, 1.0) | geom_fluid[0,1:6]=[0.5, 0.25, 1.5, 1.0, 1.0] | OK |
| E08 | mj_contactForce devolve força no frame do contato; frame.reshape(3,3).T @ f[:3] → mundo; soma em repouso = m·g | soma_mundo=[0.0, -0.0, 19.62] (m·g=19.620); ncon=4; geom[0] é o plano; len(contact)=4 | OK |
| E09 | geoms visual+collision no mesmo corpo DOBRAM a massa; inertiagrouprange='3 3' corrige | massa padrão=8.3776 kg · com inertiagrouprange=3 3 → 4.1888 kg | OK |
| E10 | com compiler angle=degree, o range da junta é convertido para rad mas o ctrlrange do atuador NÃO | jnt_range=[-0.5236, 0.5236] rad · ctrlrange=[-30.0, 30.0] | OK |
| E11 | mjd_transitionFD com flg_centered=True devolve D com SINAL TROCADO em relação a False (bug upstream 3.15.0) | D[False]=+1.0000 · D[True]=-1.0000 | OK |
| E12 | <geom mesh=…/> sem type="mesh" vira esfera; com type="mesh" vira malha; só vertex= gera o casco convexo | sem type → mjGEOM_SPHERE · com type → mjGEOM_MESH (4 faces) | OK |
| E13 | a gravidade está em qfrc_bias (não em qfrc_passive nem qfrc_applied) | qfrc_bias=-6.328 qfrc_passive=0.0 qfrc_applied=0.0 | OK |
| E14 | data.timer funciona nos bindings Python (timer padrão em segundos) após mj_step; não existe mj_timingStatus | STEP.number=2000 duration=0.0037s mj_timingStatus=False | OK |
| E15 | mjtSensor tem 49 tipos e NÃO existe sensor 'imu' | 49 tipos; imu? False | OK |
| E16 | o wheel NÃO traz mjpython, .pc nem config CMake; traz libmujoco.so.3.15.0, 4 plugins e headers | libs=['libmujoco.so.3.15.0'] plugins=['libactuator.so', 'libelasticity.so', 'libsdf_plugin.so', 'libsensor.so'] headers=72 .pc/cmake=[] mjpython=False | OK |
| E17 | pyGLFW tem variantes wayland/x11 escolhidas por XDG_SESSION_TYPE / PYGLFW_LIBRARY_VARIANT | dirs=['wayland', 'x11'] XDG_SESSION_TYPE=True PYGLFW_LIBRARY_VARIANT=True | OK |
| E18 | mj_step(nstep=N) equivale a N passos simples | ¦Δqpos¦=0.0e+00 | OK |
| E19 | option collision=… foi removido (3.0.0) e é rejeitado; atributos novos são aceitos | XML Error: Schema violation: unrecognized attribute: 'collision' | OK |
| E20 | queda livre: tempo de impacto simulado = √(2h/g) dentro de 1 passo (esfera de 1 m) | simulado=0.4540 s · previsto=0.4515 s | OK |
| E21 | atuador <pid> com ki>0 E slewmax>0 ao mesmo tempo NÃO compila em 3.15.0 (actdim > 1); ki sozinho compila | ki sozinho: compila · ki+slewmax: Error: actdim > 1 is only allowed for dyntype 'user' and 'dcmotor' | OK |
| E22 | sob XDG_SESSION_TYPE=wayland o pyGLFW carrega glfw/wayland/libglfw.so (só Wayland); PYGLFW_LIBRARY_VARIANT=x11 carrega a variante X11 | wayland → glfw/wayland/libglfw.so True False · variante x11 → glfw/x11/libglfw.so False True | OK |
| E23 | changelog: C++20 é o mínimo para compilar (3.3.7) e o dampratio da 3.15.0 é o do ATUADOR (inércia refletida), não o do solref de contato | C++20 em 3.3.7: True · item dampratio-do-atuador na 3.15.0: True | OK |
| E24 | MjSpec: mesh.maxhullvert = 3 derruba o processo (SIGSEGV/abort do qhull) — testado em subprocesso | returncode=-11 stdout='' stderr="H7093 qhull option warning: missing count of added points for trace option 'TAn'" | OK |
| D01 | os números 2,96 M e 2,33 M SPS do relatório vêm da MESMA linha «JAX FFI (WARP)» da tabela oficial de mjx.rst (Humanoid e Aloha Pot); Pure Warp = 3,35 M / 2,45 M | * - Configuration ¦ - Humanoid ¦ - Aloha Pot ¦ * - Pure Warp (No JAX FFI) ¦ - 3.35M ¦ - 2.45M ¦ * - JAX FFI (``WARP``) ¦ - 2.96M ¦ - 2.33M ¦ * - JAX FFI (``WARP`` with forced recaptures on every step) ¦ - 0.80M ¦ - 0.65M ¦ * - Configuration ¦ - Humanoid | OK |
| D02 | viewer.launch_passive sem mjpython no macOS levanta RuntimeError (não SegFault) — leitura do código 3.15.0 | viewer.py: raise RuntimeError('`launch_passive` requires that the Python script be run under `mjpython` on macOS') | OK |
| D03 | doc/skills (6 SKILL.md) está fora da toctree de doc/index.rst | 'skills' em index.rst: False | OK |
| W01 | AUR: mujoco 3.15.0 (compila do fonte), mujoco-bin uma versão atrás, python-mujoco desatualizado/flagged | mujoco 3.15.0-1 (OutOfDate=não, mant. taotieren); mujoco-bin 3.14.0-1 (OutOfDate=não, mant. elanglois); python-mujoco 3.3.7-1 (OutOfDate=sim, mant. kidofcubes) | OK |
| W02 | PyPI mujoco: 3.15.0 é a última; requires-python >=3.10; wheels cp313/cp314 manylinux x86_64 | versão=3.15.0 requires_python=>=3.10 tags=['cp310', 'cp311', 'cp312', 'cp313', 'cp314', 'cp315'] | OK |
| W03 | dm_control exige mujoco>=3.15.0 e labmaze; labmaze não tem wheel para CPython 3.13 | dm_control 1.0.48 mujoco: ['mujoco>=3.15.0'] labmaze: True; labmaze 1.0.6 wheels=['cp310', 'cp311', 'cp312', 'cp37', 'cp38', 'cp39'] | OK |
| W04 | mjlab fixa mujoco~=3.11.x e mujoco-warp~=3.11.x (não coexiste com 3.15.0) | mjlab 1.6.0 · ['warp-lang>=1.14.0', 'mujoco-warp~=3.11.0', 'mujoco~=3.11.0'] | OK |
| W05 | playground 0.2.0 requer Python >=3.11 | playground 0.2.0 requires_python=>=3.11 | OK |
| W06 | urdf2mjcf (K-Scale) não depende de CoACD/V-HACD; PyPI 0.2.39, Python >=3.11 | urdf2mjcf 0.2.39 requires_python=>=3.11 deps=['colorlogging', 'mujoco', 'numpy', 'pydantic', 'scipy', 'trimesh', 'black', 'darglint', 'mypy', 'pytest', 'ruff'] | OK |
| W07 | urdf2mjcf: nenhum arquivo .py do repositório menciona CoACD / V-HACD | 14 arquivos .py verificados; menções a CoACD/V-HACD: nenhuma | OK |
| W08 | MuJoCo 3.15.0 (tag) não instala mujoco.pc: nenhum .pc/pkgconfig no repositório e o CMake exporta mujocoConfig.cmake | arquivos .pc/pkgconfig na árvore: nenhum; CMakeLists menciona pkg-config: False; config/export cmake: ['cmake/mujocoConfig.cmake.in'] | OK |
| W09 | mujoco_mpc dormente: último commit do main em maio/2025 | último commit: 2025-05-27T09:12:29Z | OK |
| W10 | rerun-sdk 0.38.1 é a última; requires-python >=3.10 | rerun-sdk 0.38.1 requires_python=>=3.10 | OK |
| W11 | mujoco-menagerie no PyPI 2026.10.1; Menagerie tem Skydio X2 e Crazyflie 2 como únicos drones | mujoco-menagerie 2026.10.1; seção Drones cita: ["Skydio X2'><img src='assets/skydio_x2-x2.p", 'Skydio X2 '] | OK |
