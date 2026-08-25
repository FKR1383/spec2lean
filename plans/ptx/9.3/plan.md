# PTX 9.3 formalization plan

Canonical data: `plan.json`.

## Summary

- Formalization units: 29
- Instruction units: 0
- Dependency edges: 60 (0 explicit, 60 inferred)
- SCCs: 29 (0 cyclic)
- Processing layers: 5
- Source nodes referenced: 87

## Processing layers

### Layer 0

- `ptx.architecture` — Architecture (ARCHITECTURE)

### Layer 1

- `ptx.state_model` — Machine State Model (STATE_MODEL)

### Layer 2

- `ptx.directives` — Directives (DIRECTIVE)
- `ptx.execution_model` — Execution Model (EXECUTION_MODEL)
- `ptx.type_system` — Type System (TYPE_SYSTEM)

### Layer 3

- `ptx.instruction.comparison_and_selection` — Comparison and Selection Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.control_flow` — Control Flow Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.floating_point` — Floating Point Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.half_precision_comparison` — Half Precision Comparison Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.half_precision_floating_point` — Half-Precision Floating-Point Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.miscellaneous` — Miscellaneous Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.stack_manipulation` — Stack Manipulation Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.video` — Video Instructions (INSTRUCTION_FAMILY)
- `ptx.memory_model` — Memory Consistency Model (MEMORY_MODEL)
- `ptx.operand_model` — Operand Model (OPERAND_MODEL)
- `ptx.special_register` — Special Registers (SPECIAL_REGISTER)

### Layer 4

- `ptx.abi` — ABI (ABI)
- `ptx.instruction.asynchronous_warpgroup_matrix` — Asynchronous Warpgroup Matrix Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.data_movement_conversion` — Data Movement and Conversion Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.extended_precision_integer_arithmetic` — Extended-Precision Integer Arithmetic Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.fabric` — Fabric Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.integer_arithmetic` — Integer Arithmetic Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.logic_and_shift` — Logic and Shift Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.mixed_precision_floating_point` — Mixed Precision Floating-Point Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.parallel_synchronization_and_communication` — Parallel Synchronization and Communication Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.surface` — Surface Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.tensorcore_5th_generation` — TensorCore 5th Generation Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.texture` — Texture Instructions (INSTRUCTION_FAMILY)
- `ptx.instruction.warp_level_matrix` — Warp-Level Matrix Instructions (INSTRUCTION_FAMILY)

## Dependencies

- `ptx.architecture` → `ptx.abi` (USES_TYPE_SYSTEM, INFERRED): ABI mappings depend on target architecture and supported type/state-space capabilities.
- `ptx.architecture` → `ptx.directives` (USES_EXECUTION_MODEL, INFERRED): Directive handling depends on target architecture versions and features.
- `ptx.architecture` → `ptx.state_model` (USES_STATE_MODEL, INFERRED): State model refines machine and architectural state assumptions.
- `ptx.execution_model` → `ptx.instruction.asynchronous_warpgroup_matrix` (USES_EXECUTION_MODEL, INFERRED): Async warpgroup matrix instructions depend on asynchronous execution grouping and scheduling.
- `ptx.execution_model` → `ptx.instruction.comparison_and_selection` (USES_EXECUTION_MODEL, INFERRED): These instructions control predicate values in execution flow.
- `ptx.execution_model` → `ptx.instruction.control_flow` (USES_EXECUTION_MODEL, INFERRED): Control-flow opcodes directly manipulate instruction stream progression.
- `ptx.execution_model` → `ptx.instruction.data_movement_conversion` (USES_EXECUTION_MODEL, INFERRED): Async copy and conversion forms interact with execution ordering and completion.
- `ptx.execution_model` → `ptx.instruction.extended_precision_integer_arithmetic` (USES_EXECUTION_MODEL, INFERRED): Carry/CC instructions depend on predication and instruction sequencing.
- `ptx.execution_model` → `ptx.instruction.fabric` (USES_EXECUTION_MODEL, INFERRED): Fabric operations follow the PTX execution and proxy/handle lifecycle model.
- `ptx.execution_model` → `ptx.instruction.floating_point` (USES_EXECUTION_MODEL, INFERRED): Floating-point instructions execute under arithmetic and predicate rules.
- `ptx.execution_model` → `ptx.instruction.half_precision_floating_point` (USES_EXECUTION_MODEL, INFERRED): Half-precision FP instructions obey standard execution and rounding semantics.
- `ptx.execution_model` → `ptx.instruction.integer_arithmetic` (USES_EXECUTION_MODEL, INFERRED): Integer arithmetic instructions execute under the PTX control-flow and predication model.
- `ptx.execution_model` → `ptx.instruction.logic_and_shift` (USES_EXECUTION_MODEL, INFERRED): Bitwise instructions are plain operations under ALU/control model.
- `ptx.execution_model` → `ptx.instruction.miscellaneous` (USES_EXECUTION_MODEL, INFERRED): Misc instructions interact with trap/debugging behavior and execution control.
- `ptx.execution_model` → `ptx.instruction.parallel_synchronization_and_communication` (USES_EXECUTION_MODEL, INFERRED): Synchronization instructions directly affect active thread-group execution semantics.
- `ptx.execution_model` → `ptx.instruction.stack_manipulation` (USES_EXECUTION_MODEL, INFERRED): Stack instructions affect call/return stack-like state during execution.
- `ptx.execution_model` → `ptx.instruction.surface` (USES_EXECUTION_MODEL, INFERRED): Surface accesses are ordered according to surface and execution model.
- `ptx.execution_model` → `ptx.instruction.tensorcore_5th_generation` (USES_EXECUTION_MODEL, INFERRED): TCGEN05 instructions are asynchronous and grouped across threads/CTAs.
- `ptx.execution_model` → `ptx.instruction.texture` (USES_EXECUTION_MODEL, INFERRED): Texture operations are execution-space dependent instructions.
- `ptx.execution_model` → `ptx.instruction.video` (USES_EXECUTION_MODEL, INFERRED): Video vector instructions map to execution functional units and predication behavior.
- `ptx.execution_model` → `ptx.instruction.warp_level_matrix` (USES_EXECUTION_MODEL, INFERRED): Warp-level tensor operations rely on warp scheduling and execution group behavior.
- `ptx.execution_model` → `ptx.memory_model` (USES_MEMORY_MODEL, INFERRED): Execution ordering interacts with memory consistency rules.
- `ptx.execution_model` → `ptx.special_register` (USES_EXECUTION_MODEL, INFERRED): Special register reads occur according to execution context and thread hierarchy.
- `ptx.memory_model` → `ptx.instruction.asynchronous_warpgroup_matrix` (USES_MEMORY_MODEL, INFERRED): Uses async proxy and shared memory lifecycles with ordering constraints.
- `ptx.memory_model` → `ptx.instruction.data_movement_conversion` (USES_MEMORY_MODEL, INFERRED): Load/store/copy operations require memory consistency and state-space rules.
- `ptx.memory_model` → `ptx.instruction.fabric` (USES_MEMORY_MODEL, INFERRED): Fabric operations are memory and communication operations with completion semantics.
- `ptx.memory_model` → `ptx.instruction.parallel_synchronization_and_communication` (USES_MEMORY_MODEL, INFERRED): Synchronization and atomic operations constrain memory visibility.
- `ptx.memory_model` → `ptx.instruction.surface` (USES_MEMORY_MODEL, INFERRED): Surface loads/stores participate in memory consistency.
- `ptx.memory_model` → `ptx.instruction.tensorcore_5th_generation` (USES_MEMORY_MODEL, INFERRED): These instructions integrate tensor memory consistency and smem access rules.
- `ptx.memory_model` → `ptx.instruction.texture` (USES_MEMORY_MODEL, INFERRED): Texture instructions access image objects and memory-like resources.
- `ptx.memory_model` → `ptx.instruction.warp_level_matrix` (USES_MEMORY_MODEL, INFERRED): Warp-level matrix instructions load/store tensor layouts and share memory.
- `ptx.operand_model` → `ptx.abi` (USES_STATE_MODEL, INFERRED): Function ABI depends on operand/result conventions and declared parameter forms.
- `ptx.operand_model` → `ptx.instruction.data_movement_conversion` (USES_OPERAND_MODEL, INFERRED): Address and register-operands for data movement are modelled in operand syntax.
- `ptx.operand_model` → `ptx.instruction.extended_precision_integer_arithmetic` (USES_OPERAND_MODEL, INFERRED): Extended precision variants require constrained destination/source operands.
- `ptx.operand_model` → `ptx.instruction.integer_arithmetic` (USES_OPERAND_MODEL, INFERRED): Arithmetic family semantics depends on operand constraints and register forms.
- `ptx.operand_model` → `ptx.instruction.logic_and_shift` (USES_OPERAND_MODEL, INFERRED): Shifts/bitwise instructions follow source/destination operand classes.
- `ptx.operand_model` → `ptx.instruction.mixed_precision_floating_point` (USES_OPERAND_MODEL, INFERRED): Mixed-precision spellings follow shared operand and modifier conventions.
- `ptx.state_model` → `ptx.abi` (USES_STATE_MODEL, INFERRED): ABI declarations reference parameter/state-space and call/return behavior of the machine state.
- `ptx.state_model` → `ptx.directives` (USES_STATE_MODEL, INFERRED): Directives control code generation and linkage in the context of machine state.
- `ptx.state_model` → `ptx.directives` (USES_TYPE_SYSTEM, INFERRED): Directives describe ABI and metadata tied to typed declarations.
- `ptx.state_model` → `ptx.execution_model` (USES_EXECUTION_MODEL, INFERRED): Execution ordering and control depend on machine state constructs.
- `ptx.state_model` → `ptx.instruction.control_flow` (USES_STATE_MODEL, INFERRED): Control transfer depends on register/predicate state.
- `ptx.state_model` → `ptx.instruction.stack_manipulation` (USES_STATE_MODEL, INFERRED): Stack instructions manipulate compiler-visible state slots and pointer metadata.
- `ptx.state_model` → `ptx.memory_model` (USES_MEMORY_MODEL, INFERRED): Memory model constrains state-space allocation and visibility.
- `ptx.state_model` → `ptx.special_register` (USES_STATE_MODEL, INFERRED): Special register names model per-thread and system state values.
- `ptx.state_model` → `ptx.type_system` (USES_TYPE_SYSTEM, INFERRED): Types are defined as part of modelled state and instruction-visible value domains.
- `ptx.type_system` → `ptx.instruction.asynchronous_warpgroup_matrix` (USES_TYPE_SYSTEM, INFERRED): Asynchronous warpgroup MMA instructions are type/precision specific.
- `ptx.type_system` → `ptx.instruction.comparison_and_selection` (USES_TYPE_SYSTEM, INFERRED): Predication and comparison instructions are type-specific.
- `ptx.type_system` → `ptx.instruction.data_movement_conversion` (USES_TYPE_SYSTEM, INFERRED): Load/store/conversion instructions are type-indexed.
- `ptx.type_system` → `ptx.instruction.extended_precision_integer_arithmetic` (USES_TYPE_SYSTEM, INFERRED): Extended-precision integer forms require carry/type behavior rules.
- `ptx.type_system` → `ptx.instruction.floating_point` (USES_TYPE_SYSTEM, INFERRED): Floating-point instructions are defined by operand and operation types.
- `ptx.type_system` → `ptx.instruction.half_precision_comparison` (USES_TYPE_SYSTEM, INFERRED): Half-precision comparators operate on half-precision typed inputs.
- `ptx.type_system` → `ptx.instruction.half_precision_floating_point` (USES_TYPE_SYSTEM, INFERRED): Half-precision family uses extended FP16/BF16 type domains.
- `ptx.type_system` → `ptx.instruction.integer_arithmetic` (USES_TYPE_SYSTEM, INFERRED): Arithmetic instruction families are typed by destination/source types.
- `ptx.type_system` → `ptx.instruction.logic_and_shift` (USES_TYPE_SYSTEM, INFERRED): Bitwise instructions are constrained by integer type widths and predicates.
- `ptx.type_system` → `ptx.instruction.mixed_precision_floating_point` (USES_TYPE_SYSTEM, INFERRED): Mixed-precision operations are constrained by source and destination type conversions.
- `ptx.type_system` → `ptx.instruction.tensorcore_5th_generation` (USES_TYPE_SYSTEM, INFERRED): TC instructions require specific matrix, accumulator, and descriptor type schemas.
- `ptx.type_system` → `ptx.instruction.video` (USES_TYPE_SYSTEM, INFERRED): Video instructions are type-specialized across integer and FP-like packings.
- `ptx.type_system` → `ptx.instruction.warp_level_matrix` (USES_TYPE_SYSTEM, INFERRED): Matrix instructions require specific operand element-type and accumulator type constraints.
- `ptx.type_system` → `ptx.operand_model` (USES_OPERAND_MODEL, INFERRED): Operands carry explicit type information for each operand position.
