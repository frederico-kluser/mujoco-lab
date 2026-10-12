/* firmware/cross/qemu/arranque.S — arranque bare-metal ARMv7E-M (Cortex-M4 e M7) para as imagens do QEMU (mps2-an386 / mps2-an500).
 *
 * Tabela de vetores (SP inicial, Reset, NMI, HardFault, MemManage, BusFault, UsageFault, SVC, …), reset handler (ativa a FPU
 * via CPACR ANTES de qualquer instrução VFP, copia .data da «flash» para a RAM, zera .bss e chama alvo_principal()) e um
 * handler de falhas comum que chama alvo_falha(n) (escreve «FALHA n» e termina com código ≠ 0). Sem libc, sem construtores
 * estáticos (o núcleo não os tem: o teste_nucleo.py audita-o). O mapa de memória é o do QEMU (ver mps2.ld). */
    .syntax unified
    .thumb
    .cpu cortex-m4

    .section .vectors, "a", %progbits
    .align 2
    .global __vetores
__vetores:
    .word _pilha_topo
    .word reset_handler
    .word falha_nmi
    .word falha_hard
    .word falha_mem
    .word falha_bus
    .word falha_uso
    .word 0, 0, 0, 0
    .word falha_svc
    .word falha_dbg
    .word 0
    .word falha_pendsv
    .word falha_systick

    .text
    .thumb_func
    .global reset_handler
    .type reset_handler, %function
reset_handler:
    ldr r0, =0xE000ED88          /* CPACR: CP10 e CP11 em acesso total (a FPU) */
    ldr r1, [r0]
    orr r1, r1, #0x00F00000
    str r1, [r0]
    dsb
    isb
    ldr sp, =_pilha_topo
    ldr r0, =_sdata              /* .data: LMA (flash) → VMA (RAM) */
    ldr r1, =_edata
    ldr r2, =_ldata
1:  cmp r0, r1
    bhs 2f
    ldr r3, [r2], #4
    str r3, [r0], #4
    b 1b
2:  ldr r0, =_sbss               /* .bss a zero */
    ldr r1, =_ebss
    movs r3, #0
3:  cmp r0, r1
    bhs 4f
    str r3, [r0], #4
    b 3b
4:  bl alvo_principal
5:  b 5b

    .macro FALHA nome, n
    .thumb_func
    .global \nome
    .type \nome, %function
\nome:
    movs r0, #\n
    bl alvo_falha
    b .
    .endm

    FALHA falha_nmi, 2
    FALHA falha_hard, 3
    FALHA falha_mem, 4
    FALHA falha_bus, 5
    FALHA falha_uso, 6
    FALHA falha_svc, 11
    FALHA falha_dbg, 12
    FALHA falha_pendsv, 14
    FALHA falha_systick, 15
    .ltorg
