/* firmware/cross/qemu/mps2.ld — mapa de memória das máquinas mps2-an386 (Cortex-M4) e mps2-an500 (Cortex-M7) do QEMU:
 * ZBT SSRAM1 em 0x00000000 (4 MB, «flash»/código) e SSRAM2/3 em 0x20000000 (4+4 MB, RAM; confirmado com `info mtree`). */
ENTRY(reset_handler)
MEMORY
{
    CODIGO (rx)  : ORIGIN = 0x00000000, LENGTH = 4M
    RAM    (rwx) : ORIGIN = 0x20000000, LENGTH = 4M
}
_pilha_topo = ORIGIN(RAM) + LENGTH(RAM);
SECTIONS
{
    .vectors : { KEEP(*(.vectors)) } > CODIGO
    .text : { *(.text .text.*) *(.rodata .rodata.*) . = ALIGN(4); } > CODIGO
    _ldata = LOADADDR(.data);
    .data : { _sdata = .; *(.data .data.*) . = ALIGN(4); _edata = .; } > RAM AT > CODIGO
    .bss (NOLOAD) : { _sbss = .; *(.bss .bss.*) *(COMMON) . = ALIGN(4); _ebss = .; } > RAM
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment) *(.note*) }
}
