# Generated Lean Code: Every Nonblank Line Explained

Every nonblank source line is reproduced once with its original line number. The sentence after it explains that exact line. Blank lines only separate declarations and have no semantic effect.

Quick notation: `:=` starts a definition, `->` is a function type, `let` binds an immutable local, `match` selects a constructor branch, `some`/`none` represent success/failure in `Option`, and `{ old with ... }` returns an updated record rather than mutating it.

## 1. ArithmeticUpdates.lean — x86 ADD, DEC, and INC

Source: `translations/x86/092/plan:187bacc4e2041638a8ba2017/ArithmeticUpdates/ArithmeticUpdates.lean`

**L1** `import Std` — Imports Lean's standard library.

**L3** `namespace Spec2Lean.X86.ArithmeticUpdates` — Opens namespace `Spec2Lean.X86.ArithmeticUpdates`; following names receive this prefix.

**L5** `inductive Width where` — Begins closed datatype `Width`; following lines list its constructors.

**L6** `  | w8` — Declares constructor `w8` of the datatype currently being defined.

**L7** `  | w16` — Declares constructor `w16` of the datatype currently being defined.

**L8** `  | w32` — Declares constructor `w32` of the datatype currently being defined.

**L9** `  | w64` — Declares constructor `w64` of the datatype currently being defined.

**L10** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L12** `def Width.bits : Width -> Nat` — Begins function `Width.bits`; its signature/body continues below.

**L13** `  | .w8 => 8` — Match branch: input pattern `.w8` produces/evaluates `8`.

**L14** `  | .w16 => 16` — Match branch: input pattern `.w16` produces/evaluates `16`.

**L15** `  | .w32 => 32` — Match branch: input pattern `.w32` produces/evaluates `32`.

**L16** `  | .w64 => 64` — Match branch: input pattern `.w64` produces/evaluates `64`.

**L18** `def widthLe (a b : Width) : Bool := decide (a.bits <= b.bits)` — Defines a Boolean width comparison; `decide` converts the proposition “a's bit count is at most b's” into `Bool`.

**L19** `def modulus (w : Width) : Nat := 2 ^ w.bits` — Defines the fixed-width modulus as two raised to the selected bit count.

**L20** `def signBit (w : Width) : Nat := 2 ^ (w.bits - 1)` — Defines the numeric mask/value of the selected width's highest bit.

**L22** `structure Value (w : Width) where` — Begins record type `Value`; following lines list its fields.

**L23** `  toNat : Nat` — Declares field/parameter `toNat` with type `Nat`.

**L24** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L26** `def mkValue (w : Width) (n : Nat) : Value w := ⟨n % modulus w⟩` — Constructs a width-indexed value after reducing `n` modulo `2^width`, which implements wraparound.

**L28** `inductive Location where` — Begins closed datatype `Location`; following lines list its constructors.

**L29** `  | register (index : Nat)` — Declares constructor `register (index : Nat)` of the datatype currently being defined.

**L30** `  | memory (address : Nat)` — Declares constructor `memory (address : Nat)` of the datatype currently being defined.

**L31** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L33** `structure Immediate where` — Begins record type `Immediate`; following lines list its fields.

**L34** `  width : Width` — Declares field/parameter `width` with type `Width`.

**L35** `  value : Value width` — Declares field/parameter `value` with type `Value width`.

**L36** `  deriving Repr` — Generates printable-representation support for the datatype/structure above.

**L38** `inductive AddSource where` — Begins closed datatype `AddSource`; following lines list its constructors.

**L39** `  | immediate (value : Immediate)` — Declares constructor `immediate (value : Immediate)` of the datatype currently being defined.

**L40** `  | register (index : Nat)` — Declares constructor `register (index : Nat)` of the datatype currently being defined.

**L41** `  | memory (address : Nat)` — Declares constructor `memory (address : Nat)` of the datatype currently being defined.

**L42** `  deriving Repr` — Generates printable-representation support for the datatype/structure above.

**L44** `structure Flags where` — Begins record type `Flags`; following lines list its fields.

**L45** `  ofl : Bool` — Declares field/parameter `ofl` with type `Bool`.

**L46** `  sf : Bool` — Declares field/parameter `sf` with type `Bool`.

**L47** `  zf : Bool` — Declares field/parameter `zf` with type `Bool`.

**L48** `  af : Bool` — Declares field/parameter `af` with type `Bool`.

**L49** `  cf : Bool` — Declares field/parameter `cf` with type `Bool`.

**L50** `  pf : Bool` — Declares field/parameter `pf` with type `Bool`.

**L51** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L53** `structure MachineState where` — Begins record type `MachineState`; following lines list its fields.

**L54** `  registers : Nat -> Nat` — Declares field/parameter `registers` with type `Nat -> Nat`.

**L55** `  memory : Nat -> Nat` — Declares field/parameter `memory` with type `Nat -> Nat`.

**L56** `  flags : Flags` — Declares field/parameter `flags` with type `Flags`.

**L58** `inductive Mode where` — Begins closed datatype `Mode`; following lines list its constructors.

**L59** `  | legacy` — Declares constructor `legacy` of the datatype currently being defined.

**L60** `  | long` — Declares constructor `long` of the datatype currently being defined.

**L61** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L63** `inductive UnaryEncoding where` — Begins closed datatype `UnaryEncoding`; following lines list its constructors.

**L64** `  | modRM` — Declares constructor `modRM` of the datatype currently being defined.

**L65** `  | opcodeRegister` — Declares constructor `opcodeRegister` of the datatype currently being defined.

**L66** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L68** `structure AddForm where` — Begins record type `AddForm`; following lines list its fields.

**L69** `  width : Width` — Declares field/parameter `width` with type `Width`.

**L70** `  mode : Mode` — Declares field/parameter `mode` with type `Mode`.

**L71** `  rexW : Bool` — Declares field/parameter `rexW` with type `Bool`.

**L72** `  rexR : Bool` — Declares field/parameter `rexR` with type `Bool`.

**L73** `  lock : Bool` — Declares field/parameter `lock` with type `Bool`.

**L74** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L76** `structure DecForm where` — Begins record type `DecForm`; following lines list its fields.

**L77** `  width : Width` — Declares field/parameter `width` with type `Width`.

**L78** `  mode : Mode` — Declares field/parameter `mode` with type `Mode`.

**L79** `  encoding : UnaryEncoding` — Declares field/parameter `encoding` with type `UnaryEncoding`.

**L80** `  rexW : Bool` — Declares field/parameter `rexW` with type `Bool`.

**L81** `  rexR : Bool` — Declares field/parameter `rexR` with type `Bool`.

**L82** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L84** `structure IncForm where` — Begins record type `IncForm`; following lines list its fields.

**L85** `  width : Width` — Declares field/parameter `width` with type `Width`.

**L86** `  mode : Mode` — Declares field/parameter `mode` with type `Mode`.

**L87** `  encoding : UnaryEncoding` — Declares field/parameter `encoding` with type `UnaryEncoding`.

**L88** `  rexW : Bool` — Declares field/parameter `rexW` with type `Bool`.

**L89** `  rexR : Bool` — Declares field/parameter `rexR` with type `Bool`.

**L90** `  lock : Bool` — Declares field/parameter `lock` with type `Bool`.

**L91** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L93** `inductive Fault where` — Begins closed datatype `Fault`; following lines list its constructors.

**L94** `  | invalidEncoding` — Declares constructor `invalidEncoding` of the datatype currently being defined.

**L95** `  | invalidOperand` — Declares constructor `invalidOperand` of the datatype currently being defined.

**L96** `  | undefinedInstruction` — Declares constructor `undefinedInstruction` of the datatype currently being defined.

**L97** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L99** `inductive ExecResult where` — Begins closed datatype `ExecResult`; following lines list its constructors.

**L100** `  | success (state : MachineState) (atomicMemoryUpdate : Bool)` — Declares constructor `success (state : MachineState) (atomicMemoryUpdate : Bool)` of the datatype currently being defined.

**L101** `  | fault (kind : Fault)` — Declares constructor `fault (kind : Fault)` of the datatype currently being defined.

**L103** `def readLocation (w : Width) (loc : Location) (st : MachineState) : Value w :=` — Begins definition `readLocation`; `:=` ends the signature and the indented body follows.

**L104** `  match loc with` — Starts pattern matching; one following constructor branch will be selected.

**L105** `  | .register i => mkValue w (st.registers i)` — Match branch: input pattern `.register i` produces/evaluates `mkValue w (st.registers i)`.

**L106** `  | .memory a => mkValue w (st.memory a)` — Match branch: input pattern `.memory a` produces/evaluates `mkValue w (st.memory a)`.

**L108** `def writeLocation (w : Width) (loc : Location) (value : Value w)` — Begins function `writeLocation`; its signature/body continues below.

**L109** `    (st : MachineState) : MachineState :=` — Finishes the multiline function signature and starts its body after `:=`.

**L110** `  let n := value.toNat % modulus w` — Binds immutable local `n` to `value.toNat % modulus w`.

**L111** `  match loc with` — Starts pattern matching; one following constructor branch will be selected.

**L112** `  | .register i => { st with registers := fun j => if j = i then n else st.registers j }` — Match branch: input pattern `.register i` produces/evaluates `{ st with registers := fun j => if j = i then n else st.registers j }`.

**L113** `  | .memory a => { st with memory := fun b => if b = a then n else st.memory b }` — Match branch: input pattern `.memory a` produces/evaluates `{ st with memory := fun b => if b = a then n else st.memory b }`.

**L115** `def signExtendImmediate (destinationWidth : Width) (imm : Immediate) : Value destinationWidth :=` — Begins definition `signExtendImmediate`; `:=` ends the signature and the indented body follows.

**L116** `  let x := imm.value.toNat % modulus imm.width` — Binds immutable local `x` to `imm.value.toNat % modulus imm.width`.

**L117** `  if x < signBit imm.width then` — Tests condition `x < signBit imm.width`; following code is its true branch.

**L118** `    mkValue destinationWidth x` — Constructs the destination-width value from the unchanged nonnegative immediate.

**L119** `  else` — Starts the false branch of the preceding conditional.

**L120** `    mkValue destinationWidth (modulus destinationWidth - (modulus imm.width - x))` — Constructs the destination-width two's-complement pattern for a negative immediate.

**L122** `def readAddSource (w : Width) (src : AddSource) (st : MachineState) : Option (Value w) :=` — Begins definition `readAddSource`; `:=` ends the signature and the indented body follows.

**L123** `  match src with` — Starts pattern matching; one following constructor branch will be selected.

**L124** `  | .register i => some (mkValue w (st.registers i))` — Match branch: input pattern `.register i` produces/evaluates `some (mkValue w (st.registers i))`.

**L125** `  | .memory a => some (mkValue w (st.memory a))` — Match branch: input pattern `.memory a` produces/evaluates `some (mkValue w (st.memory a))`.

**L126** `  | .immediate imm =>` — Match branch: input pattern `.immediate imm` produces/evaluates ``.

**L127** `      if widthLe imm.width w then some (signExtendImmediate w imm) else none` — Tests condition `widthLe imm.width w then some (signExtendImmediate w imm) else none`; following code is its true branch.

**L129** `def parityEvenLowByte (n : Nat) : Bool :=` — Begins definition `parityEvenLowByte`; `:=` ends the signature and the indented body follows.

**L130** `  let bit (i : Nat) : Nat := if Nat.testBit n i then 1 else 0` — Binds immutable local `bit` to `if Nat.testBit n i then 1 else 0`.

**L131** `  decide ((bit 0 + bit 1 + bit 2 + bit 3 + bit 4 + bit 5 + bit 6 + bit 7) % 2 = 0)` — Adds the low eight bits and returns true exactly when the number of set bits is even.

**L133** `def resultFlags (w : Width) (result : Value w) : Flags :=` — Begins definition `resultFlags`; `:=` ends the signature and the indented body follows.

**L134** `  let r := result.toNat % modulus w` — Binds immutable local `r` to `result.toNat % modulus w`.

**L135** `  { ofl := false` — Starts a `Flags` record with overflow initially false; later fields follow.

**L136** `    sf := decide (r >= signBit w)` — Assigns record field/local component `sf` the value `decide (r >= signBit w)`.

**L137** `    zf := decide (r = 0)` — Assigns record field/local component `zf` the value `decide (r = 0)`.

**L138** `    af := false` — Assigns record field/local component `af` the value `false`.

**L139** `    cf := false` — Assigns record field/local component `cf` the value `false`.

**L140** `    pf := parityEvenLowByte r }` — Assigns record field/local component `pf` the value `parityEvenLowByte r }`.

**L142** `def addResultFlags (w : Width) (a b result : Value w) : Flags :=` — Begins definition `addResultFlags`; `:=` ends the signature and the indented body follows.

**L143** `  let x := a.toNat % modulus w` — Binds immutable local `x` to `a.toNat % modulus w`.

**L144** `  let y := b.toNat % modulus w` — Binds immutable local `y` to `b.toNat % modulus w`.

**L145** `  let r := result.toNat % modulus w` — Binds immutable local `r` to `result.toNat % modulus w`.

**L146** `  let sx := x >= signBit w` — Binds immutable local `sx` to `x >= signBit w`.

**L147** `  let sy := y >= signBit w` — Binds immutable local `sy` to `y >= signBit w`.

**L148** `  let sr := r >= signBit w` — Binds immutable local `sr` to `r >= signBit w`.

**L149** `  { (resultFlags w result) with` — Copies the common result flags and begins overriding instruction-specific fields.

**L150** `    ofl := decide (sx = sy ∧ sr ≠ sx)` — Assigns record field/local component `ofl` the value `decide (sx = sy ∧ sr ≠ sx)`.

**L151** `    af := decide (x % 16 + y % 16 >= 16)` — Assigns record field/local component `af` the value `decide (x % 16 + y % 16 >= 16)`.

**L152** `    cf := decide (x + y >= modulus w) }` — Assigns record field/local component `cf` the value `decide (x + y >= modulus w) }`.

**L154** `def incResultFlags (w : Width) (old : Value w) (result : Value w)` — Begins function `incResultFlags`; its signature/body continues below.

**L155** `    (oldCarry : Bool) : Flags :=` — Finishes the multiline function signature and starts its body after `:=`.

**L156** `  let x := old.toNat % modulus w` — Binds immutable local `x` to `old.toNat % modulus w`.

**L157** `  { (resultFlags w result) with` — Copies the common result flags and begins overriding instruction-specific fields.

**L158** `    ofl := decide (x = signBit w - 1)` — Assigns record field/local component `ofl` the value `decide (x = signBit w - 1)`.

**L159** `    af := decide (x % 16 = 15)` — Assigns record field/local component `af` the value `decide (x % 16 = 15)`.

**L160** `    cf := oldCarry }` — Assigns record field/local component `cf` the value `oldCarry }`.

**L162** `def decResultFlags (w : Width) (old : Value w) (result : Value w)` — Begins function `decResultFlags`; its signature/body continues below.

**L163** `    (oldCarry : Bool) : Flags :=` — Finishes the multiline function signature and starts its body after `:=`.

**L164** `  let x := old.toNat % modulus w` — Binds immutable local `x` to `old.toNat % modulus w`.

**L165** `  { (resultFlags w result) with` — Copies the common result flags and begins overriding instruction-specific fields.

**L166** `    ofl := decide (x = signBit w)` — Assigns record field/local component `ofl` the value `decide (x = signBit w)`.

**L167** `    af := decide (x % 16 = 0)` — Assigns record field/local component `af` the value `decide (x % 16 = 0)`.

**L168** `    cf := oldCarry }` — Assigns record field/local component `cf` the value `oldCarry }`.

**L170** `def validSizedForm (width : Width) (mode : Mode) (rexW : Bool) : Bool :=` — Begins definition `validSizedForm`; `:=` ends the signature and the indented body follows.

**L171** `  match mode, width with` — Starts pattern matching; one following constructor branch will be selected.

**L172** `  | .legacy, .w64 => false` — Match branch: input pattern `.legacy, .w64` produces/evaluates `false`.

**L173** `  | .legacy, _ => !rexW` — Match branch: input pattern `.legacy, _` produces/evaluates `!rexW`.

**L174** `  | .long, .w64 => rexW` — Match branch: input pattern `.long, .w64` produces/evaluates `rexW`.

**L175** `  | .long, _ => !rexW` — Match branch: input pattern `.long, _` produces/evaluates `!rexW`.

**L177** `def validAddForm (form : AddForm) : Bool :=` — Begins definition `validAddForm`; `:=` ends the signature and the indented body follows.

**L178** `  validSizedForm form.width form.mode form.rexW &&` — Computes this Boolean condition and ANDs it with the condition on the next line.

**L179** `    match form.mode with` — Starts pattern matching; one following constructor branch will be selected.

**L180** `    | .legacy => !form.rexR` — Match branch: input pattern `.legacy` produces/evaluates `!form.rexR`.

**L181** `    | .long => true` — Match branch: input pattern `.long` produces/evaluates `true`.

**L183** `def validUnaryForm (width : Width) (mode : Mode) (encoding : UnaryEncoding)` — Begins function `validUnaryForm`; its signature/body continues below.

**L184** `    (rexW rexR : Bool) : Bool :=` — Finishes the multiline function signature and starts its body after `:=`.

**L185** `  validSizedForm width mode rexW &&` — Computes this Boolean condition and ANDs it with the condition on the next line.

**L186** `    (match mode with` — Continues the typed parameter/signature for form validation.

**L187** `     | .legacy => !rexR` — Match branch: input pattern `.legacy` produces/evaluates `!rexR`.

**L188** `     | .long => true) &&` — Match branch: input pattern `.long` produces/evaluates `true) &&`.

**L189** `    match encoding with` — Starts pattern matching; one following constructor branch will be selected.

**L190** `    | .modRM => true` — Match branch: input pattern `.modRM` produces/evaluates `true`.

**L191** `    | .opcodeRegister => mode = .legacy && (width = .w16 || width = .w32)` — Match branch: input pattern `.opcodeRegister` produces/evaluates `mode = .legacy && (width = .w16 || width = .w32)`.

**L193** `def ADD (w : Width) (destination source : Value w) : Value w :=` — Begins definition `ADD`; `:=` ends the signature and the indented body follows.

**L194** `  mkValue w (destination.toNat + source.toNat)` — Adds both operands and normalizes the sum modulo the selected width.

**L196** `def DEC (w : Width) (destination : Value w) : Value w :=` — Begins definition `DEC`; `:=` ends the signature and the indented body follows.

**L197** `  mkValue w (destination.toNat + modulus w - 1)` — Subtracts one without truncated natural subtraction, then normalizes modulo the width.

**L199** `def INC (w : Width) (destination : Value w) : Value w :=` — Begins definition `INC`; `:=` ends the signature and the indented body follows.

**L200** `  mkValue w (destination.toNat + 1)` — Adds one and normalizes modulo the selected width.

**L202** `def executeADD (form : AddForm) (destination : Location) (source : AddSource)` — Begins function `executeADD`; its signature/body continues below.

**L203** `    (st : MachineState) : ExecResult :=` — Finishes the multiline function signature and starts its body after `:=`.

**L204** `  if !validAddForm form then` — Tests condition `!validAddForm form`; following code is its true branch.

**L205** `    .fault .invalidEncoding` — Returns fault result `.invalidEncoding`.

**L206** `  else if form.lock && (match destination with | .memory _ => false | _ => true) then` — After earlier tests fail, tests `form.lock && (match destination with | .memory _ => false | _ => true)`.

**L207** `    .fault .undefinedInstruction` — Returns fault result `.undefinedInstruction`.

**L208** `  else if (match destination, source with | .memory _, .memory _ => true | _, _ => false) then` — After earlier tests fail, tests `(match destination, source with | .memory _, .memory _ => true | _, _ => false)`.

**L209** `    .fault .invalidOperand` — Returns fault result `.invalidOperand`.

**L210** `  else` — Starts the false branch of the preceding conditional.

**L211** `    match readAddSource form.width source st with` — Starts pattern matching; one following constructor branch will be selected.

**L212** `    | none => .fault .invalidOperand` — Match branch: input pattern `none` produces/evaluates `.fault .invalidOperand`.

**L213** `    | some sourceValue =>` — Match branch: input pattern `some sourceValue` produces/evaluates ``.

**L214** `        let old := readLocation form.width destination st` — Binds immutable local `old` to `readLocation form.width destination st`.

**L215** `        let result := ADD form.width old sourceValue` — Binds immutable local `result` to `ADD form.width old sourceValue`.

**L216** `        let next := writeLocation form.width destination result st` — Binds immutable local `next` to `writeLocation form.width destination result st`.

**L217** `        let next := { next with flags := addResultFlags form.width old sourceValue result }` — Binds immutable local `next` to `{ next with flags := addResultFlags form.width old sourceValue result }`.

**L218** `        .success next (form.lock && (match destination with | .memory _ => true | _ => false))` — Returns successful execution containing `next (form.lock && (match destination with | .memory _ => true | _ => false))`.

**L220** `def executeDEC (form : DecForm) (destination : Location)` — Begins function `executeDEC`; its signature/body continues below.

**L221** `    (st : MachineState) : ExecResult :=` — Finishes the multiline function signature and starts its body after `:=`.

**L222** `  if !validUnaryForm form.width form.mode form.encoding form.rexW form.rexR then` — Tests condition `!validUnaryForm form.width form.mode form.encoding form.rexW form.rexR`; following code is its true branch.

**L223** `    .fault .invalidEncoding` — Returns fault result `.invalidEncoding`.

**L224** `  else` — Starts the false branch of the preceding conditional.

**L225** `    let old := readLocation form.width destination st` — Binds immutable local `old` to `readLocation form.width destination st`.

**L226** `    let result := DEC form.width old` — Binds immutable local `result` to `DEC form.width old`.

**L227** `    let next := writeLocation form.width destination result st` — Binds immutable local `next` to `writeLocation form.width destination result st`.

**L228** `    let next := { next with flags := decResultFlags form.width old result st.flags.cf }` — Binds immutable local `next` to `{ next with flags := decResultFlags form.width old result st.flags.cf }`.

**L229** `    .success next false` — Returns successful execution containing `next false`.

**L231** `def executeINC (form : IncForm) (destination : Location)` — Begins function `executeINC`; its signature/body continues below.

**L232** `    (st : MachineState) : ExecResult :=` — Finishes the multiline function signature and starts its body after `:=`.

**L233** `  if !validUnaryForm form.width form.mode form.encoding form.rexW form.rexR then` — Tests condition `!validUnaryForm form.width form.mode form.encoding form.rexW form.rexR`; following code is its true branch.

**L234** `    .fault .invalidEncoding` — Returns fault result `.invalidEncoding`.

**L235** `  else if form.lock && (match destination with | .memory _ => false | _ => true) then` — After earlier tests fail, tests `form.lock && (match destination with | .memory _ => false | _ => true)`.

**L236** `    .fault .undefinedInstruction` — Returns fault result `.undefinedInstruction`.

**L237** `  else` — Starts the false branch of the preceding conditional.

**L238** `    let old := readLocation form.width destination st` — Binds immutable local `old` to `readLocation form.width destination st`.

**L239** `    let result := INC form.width old` — Binds immutable local `result` to `INC form.width old`.

**L240** `    let next := writeLocation form.width destination result st` — Binds immutable local `next` to `writeLocation form.width destination result st`.

**L241** `    let next := { next with flags := incResultFlags form.width old result st.flags.cf }` — Binds immutable local `next` to `{ next with flags := incResultFlags form.width old result st.flags.cf }`.

**L242** `    .success next (form.lock && (match destination with | .memory _ => true | _ => false))` — Returns successful execution containing `next (form.lock && (match destination with | .memory _ => true | _ => false))`.

**L244** `end Spec2Lean.X86.ArithmeticUpdates` — Closes namespace `Spec2Lean.X86.ArithmeticUpdates`.

## 2. LogicalAnd.lean — x86 AND

Source: `translations/x86/092/plan:187bacc4e2041638a8ba2017/LogicalAnd/LogicalAnd.lean`

**L1** `import Std` — Imports Lean's standard library.

**L3** `namespace Spec2Lean.X86.LogicalAnd` — Opens namespace `Spec2Lean.X86.LogicalAnd`; following names receive this prefix.

**L5** `inductive OperandWidth where` — Begins closed datatype `OperandWidth`; following lines list its constructors.

**L6** `  | w8` — Declares constructor `w8` of the datatype currently being defined.

**L7** `  | w16` — Declares constructor `w16` of the datatype currently being defined.

**L8** `  | w32` — Declares constructor `w32` of the datatype currently being defined.

**L9** `  | w64` — Declares constructor `w64` of the datatype currently being defined.

**L10** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L12** `def OperandWidth.bitCount : OperandWidth -> Nat` — Begins function `OperandWidth.bitCount`; its signature/body continues below.

**L13** `  | .w8 => 8` — Match branch: input pattern `.w8` produces/evaluates `8`.

**L14** `  | .w16 => 16` — Match branch: input pattern `.w16` produces/evaluates `16`.

**L15** `  | .w32 => 32` — Match branch: input pattern `.w32` produces/evaluates `32`.

**L16** `  | .w64 => 64` — Match branch: input pattern `.w64` produces/evaluates `64`.

**L18** `structure Value where` — Begins record type `Value`; following lines list its fields.

**L19** `  width : OperandWidth` — Declares field/parameter `width` with type `OperandWidth`.

**L20** `  bits : UInt64` — Declares field/parameter `bits` with type `UInt64`.

**L21** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L23** `abbrev Carry := Bool` — Makes `Carry` a transparent alias of `Bool`.

**L25** `abbrev Predicate := Bool` — Makes `Predicate` a transparent alias of `Bool`.

**L27** `inductive FlagValue where` — Begins closed datatype `FlagValue`; following lines list its constructors.

**L28** `  | defined (value : Predicate)` — Declares constructor `defined (value : Predicate)` of the datatype currently being defined.

**L29** `  | undefined` — Declares constructor `undefined` of the datatype currently being defined.

**L30** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L32** `structure StatusFlags where` — Begins record type `StatusFlags`; following lines list its fields.

**L33** `  overflow : FlagValue` — Declares field/parameter `overflow` with type `FlagValue`.

**L34** `  carry : FlagValue` — Declares field/parameter `carry` with type `FlagValue`.

**L35** `  sign : FlagValue` — Declares field/parameter `sign` with type `FlagValue`.

**L36** `  zero : FlagValue` — Declares field/parameter `zero` with type `FlagValue`.

**L37** `  parity : FlagValue` — Declares field/parameter `parity` with type `FlagValue`.

**L38** `  auxiliary : FlagValue` — Declares field/parameter `auxiliary` with type `FlagValue`.

**L39** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L41** `structure StatusFlagModel where` — Begins record type `StatusFlagModel`; following lines list its fields.

**L42** `  sign : Value -> Predicate` — Declares field/parameter `sign` with type `Value -> Predicate`.

**L43** `  zero : Value -> Predicate` — Declares field/parameter `zero` with type `Value -> Predicate`.

**L44** `  parity : Value -> Predicate` — Declares field/parameter `parity` with type `Value -> Predicate`.

**L46** `structure MachineState where` — Begins record type `MachineState`; following lines list its fields.

**L47** `  registers : Nat -> Value` — Declares field/parameter `registers` with type `Nat -> Value`.

**L48** `  memory : Nat -> Value` — Declares field/parameter `memory` with type `Nat -> Value`.

**L49** `  flags : StatusFlags` — Declares field/parameter `flags` with type `StatusFlags`.

**L51** `inductive Destination where` — Begins closed datatype `Destination`; following lines list its constructors.

**L52** `  | register (index : Nat)` — Declares constructor `register (index : Nat)` of the datatype currently being defined.

**L53** `  | memory (address : Nat)` — Declares constructor `memory (address : Nat)` of the datatype currently being defined.

**L54** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L56** `inductive Source where` — Begins closed datatype `Source`; following lines list its constructors.

**L57** `  | immediate (bits : UInt64) (encodedWidth : OperandWidth)` — Declares constructor `immediate (bits : UInt64) (encodedWidth : OperandWidth)` of the datatype currently being defined.

**L58** `      (signExtended : Bool)` — Continues the typed parameter/signature for operands, instruction, and outcome.

**L59** `  | register (index : Nat)` — Declares constructor `register (index : Nat)` of the datatype currently being defined.

**L60** `  | memory (address : Nat)` — Declares constructor `memory (address : Nat)` of the datatype currently being defined.

**L61** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L63** `inductive MachineMode where` — Begins closed datatype `MachineMode`; following lines list its constructors.

**L64** `  | legacy` — Declares constructor `legacy` of the datatype currently being defined.

**L65** `  | compatibility` — Declares constructor `compatibility` of the datatype currently being defined.

**L66** `  | mode64` — Declares constructor `mode64` of the datatype currently being defined.

**L67** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L69** `structure AndInstruction where` — Begins record type `AndInstruction`; following lines list its fields.

**L70** `  destination : Destination` — Declares field/parameter `destination` with type `Destination`.

**L71** `  source : Source` — Declares field/parameter `source` with type `Source`.

**L72** `  width : OperandWidth` — Declares field/parameter `width` with type `OperandWidth`.

**L73** `  mode : MachineMode` — Declares field/parameter `mode` with type `MachineMode`.

**L74** `  rexW : Bool` — Declares field/parameter `rexW` with type `Bool`.

**L75** `  rexR : Bool` — Declares field/parameter `rexR` with type `Bool`.

**L76** `  lock : Bool` — Declares field/parameter `lock` with type `Bool`.

**L77** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L79** `inductive Atomicity where` — Begins closed datatype `Atomicity`; following lines list its constructors.

**L80** `  | ordinary` — Declares constructor `ordinary` of the datatype currently being defined.

**L81** `  | atomicRequired` — Declares constructor `atomicRequired` of the datatype currently being defined.

**L82** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L84** `structure ExecutionOutcome where` — Begins record type `ExecutionOutcome`; following lines list its fields.

**L85** `  state : MachineState` — Declares field/parameter `state` with type `MachineState`.

**L86** `  atomicity : Atomicity` — Declares field/parameter `atomicity` with type `Atomicity`.

**L89** `def widthMask : OperandWidth -> UInt64` — Begins function `widthMask`; its signature/body continues below.

**L90** `  | .w8 => 0xFF` — Match branch: input pattern `.w8` produces/evaluates `0xFF`.

**L91** `  | .w16 => 0xFFFF` — Match branch: input pattern `.w16` produces/evaluates `0xFFFF`.

**L92** `  | .w32 => 0xFFFFFFFF` — Match branch: input pattern `.w32` produces/evaluates `0xFFFFFFFF`.

**L93** `  | .w64 => 0xFFFFFFFFFFFFFFFF` — Match branch: input pattern `.w64` produces/evaluates `0xFFFFFFFFFFFFFFFF`.

**L96** `def normalizeValue (width : OperandWidth) (bits : UInt64) : Value :=` — Begins definition `normalizeValue`; `:=` ends the signature and the indented body follows.

**L97** `  { width := width, bits := bits &&& widthMask width }` — Constructs or updates a record in one expression: `{ width := width, bits := bits &&& widthMask width }`.

**L100** `def AND (width : OperandWidth) (destination source : Value) : Value :=` — Begins definition `AND`; `:=` ends the signature and the indented body follows.

**L101** `  normalizeValue width (destination.bits &&& source.bits)` — Computes bitwise AND, then masks away bits above the operation width.

**L104** `def signExtendImmediate` — Begins function `signExtendImmediate`; its signature/body continues below.

**L105** `    (encodedWidth operationWidth : OperandWidth) (bits : UInt64) : UInt64 :=` — Finishes the multiline function signature and starts its body after `:=`.

**L106** `  let sourceMask := widthMask encodedWidth` — Binds immutable local `sourceMask` to `widthMask encodedWidth`.

**L107** `  let targetMask := widthMask operationWidth` — Binds immutable local `targetMask` to `widthMask operationWidth`.

**L108** `  let truncated := bits &&& sourceMask` — Binds immutable local `truncated` to `bits &&& sourceMask`.

**L109** `  let signBit : UInt64 :=` — Introduces an immutable local value in immediate extension.

**L110** `    match encodedWidth with` — Starts pattern matching; one following constructor branch will be selected.

**L111** `    | .w8 => 0x80` — Match branch: input pattern `.w8` produces/evaluates `0x80`.

**L112** `    | .w16 => 0x8000` — Match branch: input pattern `.w16` produces/evaluates `0x8000`.

**L113** `    | .w32 => 0x80000000` — Match branch: input pattern `.w32` produces/evaluates `0x80000000`.

**L114** `    | .w64 => 0x8000000000000000` — Match branch: input pattern `.w64` produces/evaluates `0x8000000000000000`.

**L115** `  if truncated &&& signBit != 0 then` — Tests condition `truncated &&& signBit != 0`; following code is its true branch.

**L116** `    (truncated ||| (targetMask - sourceMask)) &&& targetMask` — Continues the typed parameter/signature for immediate extension.

**L117** `  else` — Starts the false branch of the preceding conditional.

**L118** `    truncated &&& targetMask` — Returns the nonnegative immediate masked to the target width.

**L121** `def immediateFormValid` — Begins function `immediateFormValid`; its signature/body continues below.

**L122** `    (encodedWidth operationWidth : OperandWidth) (signExtended : Bool) : Bool :=` — Finishes the multiline function signature and starts its body after `:=`.

**L123** `  if signExtended then` — Tests condition `signExtended`; following code is its true branch.

**L124** `    match encodedWidth, operationWidth with` — Starts pattern matching; one following constructor branch will be selected.

**L125** `    | .w8, .w16 => true` — Match branch: input pattern `.w8, .w16` produces/evaluates `true`.

**L126** `    | .w8, .w32 => true` — Match branch: input pattern `.w8, .w32` produces/evaluates `true`.

**L127** `    | .w8, .w64 => true` — Match branch: input pattern `.w8, .w64` produces/evaluates `true`.

**L128** `    | .w32, .w64 => true` — Match branch: input pattern `.w32, .w64` produces/evaluates `true`.

**L129** `    | _, _ => false` — Match branch: input pattern `_, _` produces/evaluates `false`.

**L130** `  else` — Starts the false branch of the preceding conditional.

**L131** `    encodedWidth == operationWidth` — For a non-sign-extended form, accepts only equal encoded and operation widths.

**L134** `def readDestination (state : MachineState) : Destination -> Value` — Begins function `readDestination`; its signature/body continues below.

**L135** `  | .register index => state.registers index` — Match branch: input pattern `.register index` produces/evaluates `state.registers index`.

**L136** `  | .memory address => state.memory address` — Match branch: input pattern `.memory address` produces/evaluates `state.memory address`.

**L139** `def readSource` — Begins function `readSource`; its signature/body continues below.

**L140** `    (state : MachineState) (operationWidth : OperandWidth) : Source -> Value` — Continues the typed parameter/signature for operand access.

**L141** `  | .immediate bits encodedWidth signExtended =>` — Match branch: input pattern `.immediate bits encodedWidth signExtended` produces/evaluates ``.

**L142** `      let extended :=` — Introduces an immutable local value in operand access.

**L143** `        if signExtended then` — Tests condition `signExtended`; following code is its true branch.

**L144** `          signExtendImmediate encodedWidth operationWidth bits` — Sign-extends the immediate bits to the operation width.

**L145** `        else` — Starts the false branch of the preceding conditional.

**L146** `          bits &&& widthMask operationWidth` — Zero-extends/truncates by masking the immediate to the operation width.

**L147** `      normalizeValue operationWidth extended` — Packages the extended immediate as a normalized operation-width value.

**L148** `  | .register index => normalizeValue operationWidth (state.registers index).bits` — Match branch: input pattern `.register index` produces/evaluates `normalizeValue operationWidth (state.registers index).bits`.

**L149** `  | .memory address => normalizeValue operationWidth (state.memory address).bits` — Match branch: input pattern `.memory address` produces/evaluates `normalizeValue operationWidth (state.memory address).bits`.

**L152** `def writeDestination` — Begins function `writeDestination`; its signature/body continues below.

**L153** `    (state : MachineState) (destination : Destination) (value : Value) : MachineState :=` — Finishes the multiline function signature and starts its body after `:=`.

**L154** `  match destination with` — Starts pattern matching; one following constructor branch will be selected.

**L155** `  | .register index =>` — Match branch: input pattern `.register index` produces/evaluates ``.

**L156** `      { state with` — Starts a functional state update; all unmentioned fields remain unchanged.

**L157** `        registers := fun current =>` — Assigns record field/local component `registers` the value `fun current =>`.

**L158** `          if current = index then value else state.registers current }` — Tests condition `current = index then value else state.registers current }`; following code is its true branch.

**L159** `  | .memory address =>` — Match branch: input pattern `.memory address` produces/evaluates ``.

**L160** `      { state with` — Starts a functional state update; all unmentioned fields remain unchanged.

**L161** `        memory := fun current =>` — Assigns record field/local component `memory` the value `fun current =>`.

**L162** `          if current = address then value else state.memory current }` — Tests condition `current = address then value else state.memory current }`; following code is its true branch.

**L165** `def operandsValid : Destination -> Source -> Bool` — Begins function `operandsValid`; its signature/body continues below.

**L166** `  | .memory _, .memory _ => false` — Match branch: input pattern `.memory _, .memory _` produces/evaluates `false`.

**L167** `  | _, _ => true` — Match branch: input pattern `_, _` produces/evaluates `true`.

**L170** `def sourceWidthValid (operationWidth : OperandWidth) : Source -> Bool` — Begins function `sourceWidthValid`; its signature/body continues below.

**L171** `  | .immediate _ encodedWidth signExtended =>` — Match branch: input pattern `.immediate _ encodedWidth signExtended` produces/evaluates ``.

**L172** `      immediateFormValid encodedWidth operationWidth signExtended` — Returns whether this immediate's encoded width/extension mode is legal.

**L173** `  | _ => true` — Match branch: input pattern `_` produces/evaluates `true`.

**L176** `def modeSizeValid` — Begins function `modeSizeValid`; its signature/body continues below.

**L177** `    (mode : MachineMode) (width : OperandWidth) (rexW : Bool) : Bool :=` — Finishes the multiline function signature and starts its body after `:=`.

**L178** `  match width with` — Starts pattern matching; one following constructor branch will be selected.

**L179** `  | .w64 => mode == .mode64 && rexW` — Match branch: input pattern `.w64` produces/evaluates `mode == .mode64 && rexW`.

**L180** `  | _ => !rexW` — Match branch: input pattern `_` produces/evaluates `!rexW`.

**L183** `def select64BitModeWidth` — Begins function `select64BitModeWidth`; its signature/body continues below.

**L184** `    (rexW : Bool) (selectedNonRexWidth : Option OperandWidth := none) : OperandWidth :=` — Finishes the multiline function signature and starts its body after `:=`.

**L185** `  if rexW then` — Tests condition `rexW`; following code is its true branch.

**L186** `    .w64` — Returns the 64-bit width constructor.

**L187** `  else` — Starts the false branch of the preceding conditional.

**L188** `    match selectedNonRexWidth with` — Starts pattern matching; one following constructor branch will be selected.

**L189** `    | some width => width` — Match branch: input pattern `some width` produces/evaluates `width`.

**L190** `    | none => .w32` — Match branch: input pattern `none` produces/evaluates `.w32`.

**L193** `def registerAccessible (mode : MachineMode) (rexR : Bool) (index : Nat) : Bool :=` — Begins definition `registerAccessible`; `:=` ends the signature and the indented body follows.

**L194** `  decide (index < 8) || (mode == .mode64 && rexR && decide (index < 16))` — Allows registers 0-7 normally, or 0-15 in 64-bit mode with REX.R.

**L197** `def destinationAccessible` — Begins function `destinationAccessible`; its signature/body continues below.

**L198** `    (mode : MachineMode) (rexR : Bool) : Destination -> Bool` — Continues the typed parameter/signature for validation.

**L199** `  | .register index => registerAccessible mode rexR index` — Match branch: input pattern `.register index` produces/evaluates `registerAccessible mode rexR index`.

**L200** `  | .memory _ => true` — Match branch: input pattern `.memory _` produces/evaluates `true`.

**L203** `def sourceAccessible (mode : MachineMode) (rexR : Bool) : Source -> Bool` — Begins function `sourceAccessible`; its signature/body continues below.

**L204** `  | .register index => registerAccessible mode rexR index` — Match branch: input pattern `.register index` produces/evaluates `registerAccessible mode rexR index`.

**L205** `  | .immediate _ _ _ => true` — Match branch: input pattern `.immediate _ _ _` produces/evaluates `true`.

**L206** `  | .memory _ => true` — Match branch: input pattern `.memory _` produces/evaluates `true`.

**L209** `def instructionValid (instruction : AndInstruction) : Bool :=` — Begins definition `instructionValid`; `:=` ends the signature and the indented body follows.

**L210** `  operandsValid instruction.destination instruction.source &&` — Computes this Boolean condition and ANDs it with the condition on the next line.

**L211** `  sourceWidthValid instruction.width instruction.source &&` — Computes this Boolean condition and ANDs it with the condition on the next line.

**L212** `  modeSizeValid instruction.mode instruction.width instruction.rexW &&` — Computes this Boolean condition and ANDs it with the condition on the next line.

**L213** `  destinationAccessible instruction.mode instruction.rexR instruction.destination &&` — Computes this Boolean condition and ANDs it with the condition on the next line.

**L214** `  sourceAccessible instruction.mode instruction.rexR instruction.source` — Adds source-register accessibility as the final instruction-validity condition.

**L217** `def executeAND` — Begins function `executeAND`; its signature/body continues below.

**L218** `    (flagModel : StatusFlagModel) (instruction : AndInstruction)` — Continues the typed parameter/signature for AND execution.

**L219** `    (state : MachineState) : Option ExecutionOutcome :=` — Finishes the multiline function signature and starts its body after `:=`.

**L220** `  if instructionValid instruction then` — Tests condition `instructionValid instruction`; following code is its true branch.

**L221** `    let destinationValue := readDestination state instruction.destination` — Binds immutable local `destinationValue` to `readDestination state instruction.destination`.

**L222** `    let sourceValue := readSource state instruction.width instruction.source` — Binds immutable local `sourceValue` to `readSource state instruction.width instruction.source`.

**L223** `    let result := AND instruction.width destinationValue sourceValue` — Binds immutable local `result` to `AND instruction.width destinationValue sourceValue`.

**L224** `    let flags : StatusFlags :=` — Introduces an immutable local value in AND execution.

**L225** `      { overflow := .defined false` — Starts the new flags record and explicitly clears overflow.

**L226** `        carry := .defined false` — Assigns record field/local component `carry` the value `.defined false`.

**L227** `        sign := .defined (flagModel.sign result)` — Assigns record field/local component `sign` the value `.defined (flagModel.sign result)`.

**L228** `        zero := .defined (flagModel.zero result)` — Assigns record field/local component `zero` the value `.defined (flagModel.zero result)`.

**L229** `        parity := .defined (flagModel.parity result)` — Assigns record field/local component `parity` the value `.defined (flagModel.parity result)`.

**L230** `        auxiliary := .undefined }` — Assigns record field/local component `auxiliary` the value `.undefined }`.

**L231** `    let nextState := writeDestination { state with flags := flags }` — Binds immutable local `nextState` to `writeDestination { state with flags := flags }`.

**L232** `      instruction.destination result` — Supplies the destination and result arguments to the continued `writeDestination` call.

**L233** `    some` — Begins construction of a successful `Option.some` outcome on the following record line.

**L234** `      { state := nextState` — Starts the successful outcome record with its updated machine state.

**L235** `        atomicity := if instruction.lock then .atomicRequired else .ordinary }` — Assigns record field/local component `atomicity` the value `if instruction.lock then .atomicRequired else .ordinary }`.

**L236** `  else` — Starts the false branch of the preceding conditional.

**L237** `    none` — Returns `Option.none`, meaning the modeled operation is invalid or unavailable.

**L239** `end Spec2Lean.X86.LogicalAnd` — Closes namespace `Spec2Lean.X86.LogicalAnd`.

## 3. OperandComparison.lean — x86 CMP

Source: `translations/x86/092/plan:187bacc4e2041638a8ba2017/OperandComparison/OperandComparison.lean`

**L1** `namespace Spec2Lean.X86.OperandComparison` — Opens namespace `Spec2Lean.X86.OperandComparison`; following names receive this prefix.

**L3** `inductive OperandWidth where` — Begins closed datatype `OperandWidth`; following lines list its constructors.

**L4** `  | w8` — Declares constructor `w8` of the datatype currently being defined.

**L5** `  | w16` — Declares constructor `w16` of the datatype currently being defined.

**L6** `  | w32` — Declares constructor `w32` of the datatype currently being defined.

**L7** `  | w64` — Declares constructor `w64` of the datatype currently being defined.

**L8** `  deriving DecidableEq, BEq, Repr` — Generates propositional equality, Boolean equality, and printing support.

**L10** `def OperandWidth.bitCount : OperandWidth -> Nat` — Begins function `OperandWidth.bitCount`; its signature/body continues below.

**L11** `  | .w8 => 8` — Match branch: input pattern `.w8` produces/evaluates `8`.

**L12** `  | .w16 => 16` — Match branch: input pattern `.w16` produces/evaluates `16`.

**L13** `  | .w32 => 32` — Match branch: input pattern `.w32` produces/evaluates `32`.

**L14** `  | .w64 => 64` — Match branch: input pattern `.w64` produces/evaluates `64`.

**L16** `abbrev Carry := Bool` — Makes `Carry` a transparent alias of `Bool`.

**L18** `abbrev Predicate := Bool` — Makes `Predicate` a transparent alias of `Bool`.

**L20** `structure Value where` — Begins record type `Value`; following lines list its fields.

**L21** `  width : OperandWidth` — Declares field/parameter `width` with type `OperandWidth`.

**L22** `  bits : BitVec width.bitCount` — Declares field/parameter `bits` with type `BitVec width.bitCount`.

**L23** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L25** `inductive Mode where` — Begins closed datatype `Mode`; following lines list its constructors.

**L26** `  | legacy` — Declares constructor `legacy` of the datatype currently being defined.

**L27** `  | compatibility` — Declares constructor `compatibility` of the datatype currently being defined.

**L28** `  | long64` — Declares constructor `long64` of the datatype currently being defined.

**L29** `  deriving DecidableEq, BEq, Repr` — Generates propositional equality, Boolean equality, and printing support.

**L31** `inductive SizeSelection where` — Begins closed datatype `SizeSelection`; following lines list its constructors.

**L32** `  | byte` — Declares constructor `byte` of the datatype currently being defined.

**L33** `  | operand16` — Declares constructor `operand16` of the datatype currently being defined.

**L34** `  | defaultSize` — Declares constructor `defaultSize` of the datatype currently being defined.

**L35** `  | rexW` — Declares constructor `rexW` of the datatype currently being defined.

**L36** `  deriving DecidableEq, BEq, Repr` — Generates propositional equality, Boolean equality, and printing support.

**L38** `structure Encoding where` — Begins record type `Encoding`; following lines list its fields.

**L39** `  mode : Mode` — Declares field/parameter `mode` with type `Mode`.

**L40** `  size : SizeSelection` — Declares field/parameter `size` with type `SizeSelection`.

**L41** `  rexR : Bool` — Declares field/parameter `rexR` with type `Bool`.

**L42** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L44** `inductive OperandLocation where` — Begins closed datatype `OperandLocation`; following lines list its constructors.

**L45** `  | accumulator` — Declares constructor `accumulator` of the datatype currently being defined.

**L46** `  | register (index : Fin 16)` — Declares constructor `register (index : Fin 16)` of the datatype currently being defined.

**L47** `  | memory` — Declares constructor `memory` of the datatype currently being defined.

**L48** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L50** `structure ReadOperand where` — Begins record type `ReadOperand`; following lines list its fields.

**L51** `  value : Value` — Declares field/parameter `value` with type `Value`.

**L52** `  location : OperandLocation` — Declares field/parameter `location` with type `OperandLocation`.

**L53** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L55** `structure Immediate where` — Begins record type `Immediate`; following lines list its fields.

**L56** `  encodedWidth : OperandWidth` — Declares field/parameter `encodedWidth` with type `OperandWidth`.

**L57** `  bits : BitVec encodedWidth.bitCount` — Declares field/parameter `bits` with type `BitVec encodedWidth.bitCount`.

**L58** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L60** `inductive CmpOperands where` — Begins closed datatype `CmpOperands`; following lines list its constructors.

**L61** `  | accumulatorImmediate (accumulator : ReadOperand) (immediate : Immediate)` — Declares constructor `accumulatorImmediate (accumulator : ReadOperand) (immediate : Immediate)` of the datatype currently being defined.

**L62** `  | rmImmediate (rm : ReadOperand) (immediate : Immediate)` — Declares constructor `rmImmediate (rm : ReadOperand) (immediate : Immediate)` of the datatype currently being defined.

**L63** `  | rmRegister (rm : ReadOperand) (register : ReadOperand)` — Declares constructor `rmRegister (rm : ReadOperand) (register : ReadOperand)` of the datatype currently being defined.

**L64** `  | registerRm (register : ReadOperand) (rm : ReadOperand)` — Declares constructor `registerRm (register : ReadOperand) (rm : ReadOperand)` of the datatype currently being defined.

**L65** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L67** `structure StatusFlags where` — Begins record type `StatusFlags`; following lines list its fields.

**L68** `  cf : Carry` — Declares field/parameter `cf` with type `Carry`.

**L69** `  of : Predicate` — Declares field/parameter `of` with type `Predicate`.

**L70** `  sf : Predicate` — Declares field/parameter `sf` with type `Predicate`.

**L71** `  zf : Predicate` — Declares field/parameter `zf` with type `Predicate`.

**L72** `  af : Predicate` — Declares field/parameter `af` with type `Predicate`.

**L73** `  pf : Predicate` — Declares field/parameter `pf` with type `Predicate`.

**L74** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L76** `structure MachineState where` — Begins record type `MachineState`; following lines list its fields.

**L77** `  flags : StatusFlags` — Declares field/parameter `flags` with type `StatusFlags`.

**L78** `  registers : Nat -> UInt64` — Declares field/parameter `registers` with type `Nat -> UInt64`.

**L79** `  memory : Nat -> UInt8` — Declares field/parameter `memory` with type `Nat -> UInt8`.

**L81** `structure CmpInstruction where` — Begins record type `CmpInstruction`; following lines list its fields.

**L82** `  encoding : Encoding` — Declares field/parameter `encoding` with type `Encoding`.

**L83** `  operands : CmpOperands` — Declares field/parameter `operands` with type `CmpOperands`.

**L84** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L86** `structure ComparisonResult where` — Begins record type `ComparisonResult`; following lines list its fields.

**L87** `  temp : Value` — Declares field/parameter `temp` with type `Value`.

**L88** `  flags : StatusFlags` — Declares field/parameter `flags` with type `StatusFlags`.

**L89** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L91** `def operationWidth (encoding : Encoding) : Option OperandWidth :=` — Begins definition `operationWidth`; `:=` ends the signature and the indented body follows.

**L92** `  match encoding.size with` — Starts pattern matching; one following constructor branch will be selected.

**L93** `  | .byte => some .w8` — Match branch: input pattern `.byte` produces/evaluates `some .w8`.

**L94** `  | .operand16 => some .w16` — Match branch: input pattern `.operand16` produces/evaluates `some .w16`.

**L95** `  | .defaultSize => some .w32` — Match branch: input pattern `.defaultSize` produces/evaluates `some .w32`.

**L96** `  | .rexW =>` — Match branch: input pattern `.rexW` produces/evaluates ``.

**L97** `      match encoding.mode with` — Starts pattern matching; one following constructor branch will be selected.

**L98** `      | .long64 => some .w64` — Match branch: input pattern `.long64` produces/evaluates `some .w64`.

**L99** `      | _ => none` — Match branch: input pattern `_` produces/evaluates `none`.

**L101** `def firstOperand : CmpOperands -> ReadOperand` — Begins function `firstOperand`; its signature/body continues below.

**L102** `  | .accumulatorImmediate accumulator _ => accumulator` — Match branch: input pattern `.accumulatorImmediate accumulator _` produces/evaluates `accumulator`.

**L103** `  | .rmImmediate rm _ => rm` — Match branch: input pattern `.rmImmediate rm _` produces/evaluates `rm`.

**L104** `  | .rmRegister rm _ => rm` — Match branch: input pattern `.rmRegister rm _` produces/evaluates `rm`.

**L105** `  | .registerRm register _ => register` — Match branch: input pattern `.registerRm register _` produces/evaluates `register`.

**L107** `def locationIsRegister : OperandLocation -> Bool` — Begins function `locationIsRegister`; its signature/body continues below.

**L108** `  | .register _ => true` — Match branch: input pattern `.register _` produces/evaluates `true`.

**L109** `  | _ => false` — Match branch: input pattern `_` produces/evaluates `false`.

**L111** `def locationIsRm : OperandLocation -> Bool` — Begins function `locationIsRm`; its signature/body continues below.

**L112** `  | .register _ => true` — Match branch: input pattern `.register _` produces/evaluates `true`.

**L113** `  | .memory => true` — Match branch: input pattern `.memory` produces/evaluates `true`.

**L114** `  | .accumulator => false` — Match branch: input pattern `.accumulator` produces/evaluates `false`.

**L116** `def locationsAllowed : CmpOperands -> Bool` — Begins function `locationsAllowed`; its signature/body continues below.

**L117** `  | .accumulatorImmediate accumulator _ =>` — Match branch: input pattern `.accumulatorImmediate accumulator _` produces/evaluates ``.

**L118** `      match accumulator.location with` — Starts pattern matching; one following constructor branch will be selected.

**L119** `      | .accumulator => true` — Match branch: input pattern `.accumulator` produces/evaluates `true`.

**L120** `      | _ => false` — Match branch: input pattern `_` produces/evaluates `false`.

**L121** `  | .rmImmediate rm _ => locationIsRm rm.location` — Match branch: input pattern `.rmImmediate rm _` produces/evaluates `locationIsRm rm.location`.

**L122** `  | .rmRegister rm register =>` — Match branch: input pattern `.rmRegister rm register` produces/evaluates ``.

**L123** `      locationIsRm rm.location && locationIsRegister register.location` — Requires the first operand to be r/m and the second to be a register.

**L124** `  | .registerRm register rm =>` — Match branch: input pattern `.registerRm register rm` produces/evaluates ``.

**L125** `      locationIsRegister register.location && locationIsRm rm.location` — Requires the first operand to be a register and the second to be r/m.

**L127** `def registerAllowed (encoding : Encoding) : OperandLocation -> Bool` — Begins function `registerAllowed`; its signature/body continues below.

**L128** `  | .register index =>` — Match branch: input pattern `.register index` produces/evaluates ``.

**L129** `      decide (index.val < 8) || (encoding.mode == .long64 && encoding.rexR)` — Allows a low register, or an extended register only in long mode with REX.R.

**L130** `  | _ => true` — Match branch: input pattern `_` produces/evaluates `true`.

**L132** `def registersAllowed (encoding : Encoding) : CmpOperands -> Bool` — Begins function `registersAllowed`; its signature/body continues below.

**L133** `  | .accumulatorImmediate accumulator _ => registerAllowed encoding accumulator.location` — Match branch: input pattern `.accumulatorImmediate accumulator _` produces/evaluates `registerAllowed encoding accumulator.location`.

**L134** `  | .rmImmediate rm _ => registerAllowed encoding rm.location` — Match branch: input pattern `.rmImmediate rm _` produces/evaluates `registerAllowed encoding rm.location`.

**L135** `  | .rmRegister rm register =>` — Match branch: input pattern `.rmRegister rm register` produces/evaluates ``.

**L136** `      registerAllowed encoding rm.location && registerAllowed encoding register.location` — Checks register availability for both operands of the r/m-register layout.

**L137** `  | .registerRm register rm =>` — Match branch: input pattern `.registerRm register rm` produces/evaluates ``.

**L138** `      registerAllowed encoding register.location && registerAllowed encoding rm.location` — Checks register availability for both operands of the register-r/m layout.

**L140** `def immediateWidthAllowed (target encoded : OperandWidth) : Bool :=` — Begins definition `immediateWidthAllowed`; `:=` ends the signature and the indented body follows.

**L141** `  match target, encoded with` — Starts pattern matching; one following constructor branch will be selected.

**L142** `  | .w8, .w8 => true` — Match branch: input pattern `.w8, .w8` produces/evaluates `true`.

**L143** `  | .w16, .w8 | .w16, .w16 => true` — Match branch: input pattern `.w16, .w8 | .w16, .w16` produces/evaluates `true`.

**L144** `  | .w32, .w8 | .w32, .w32 => true` — Match branch: input pattern `.w32, .w8 | .w32, .w32` produces/evaluates `true`.

**L145** `  | .w64, .w8 | .w64, .w32 => true` — Match branch: input pattern `.w64, .w8 | .w64, .w32` produces/evaluates `true`.

**L146** `  | _, _ => false` — Match branch: input pattern `_, _` produces/evaluates `false`.

**L148** `def modulus (width : OperandWidth) : Nat :=` — Begins definition `modulus`; `:=` ends the signature and the indented body follows.

**L149** `  2 ^ width.bitCount` — Computes the fixed-width arithmetic modulus.

**L151** `def signBit (width : OperandWidth) (value : Nat) : Bool :=` — Begins definition `signBit`; `:=` ends the signature and the indented body follows.

**L152** `  Nat.testBit value (width.bitCount - 1)` — Returns whether the value's highest active bit is set.

**L154** `def signExtendImmediate (target : OperandWidth) (immediate : Immediate) : Option Nat :=` — Begins definition `signExtendImmediate`; `:=` ends the signature and the indented body follows.

**L155** `  if immediateWidthAllowed target immediate.encodedWidth then` — Tests condition `immediateWidthAllowed target immediate.encodedWidth`; following code is its true branch.

**L156** `    let value := immediate.bits.toNat` — Binds immutable local `value` to `immediate.bits.toNat`.

**L157** `    if signBit immediate.encodedWidth value then` — Tests condition `signBit immediate.encodedWidth value`; following code is its true branch.

**L158** `      some (value + modulus target - modulus immediate.encodedWidth)` — Wraps `(value + modulus target - modulus immediate.encodedWidth)` in successful `Option.some`.

**L159** `    else` — Starts the false branch of the preceding conditional.

**L160** `      some value` — Wraps `value` in successful `Option.some`.

**L161** `  else` — Starts the false branch of the preceding conditional.

**L162** `    none` — Returns `Option.none`, meaning the modeled operation is invalid or unavailable.

**L164** `def secondOperandValue (target : OperandWidth) : CmpOperands -> Option Nat` — Begins function `secondOperandValue`; its signature/body continues below.

**L165** `  | .accumulatorImmediate _ immediate => signExtendImmediate target immediate` — Match branch: input pattern `.accumulatorImmediate _ immediate` produces/evaluates `signExtendImmediate target immediate`.

**L166** `  | .rmImmediate _ immediate => signExtendImmediate target immediate` — Match branch: input pattern `.rmImmediate _ immediate` produces/evaluates `signExtendImmediate target immediate`.

**L167** `  | .rmRegister _ register =>` — Match branch: input pattern `.rmRegister _ register` produces/evaluates ``.

**L168** `      if register.value.width == target then some register.value.bits.toNat else none` — Tests condition `register.value.width == target then some register.value.bits.toNat else none`; following code is its true branch.

**L169** `  | .registerRm _ rm =>` — Match branch: input pattern `.registerRm _ rm` produces/evaluates ``.

**L170** `      if rm.value.width == target then some rm.value.bits.toNat else none` — Tests condition `rm.value.width == target then some rm.value.bits.toNat else none`; following code is its true branch.

**L172** `def evenParityLowByte (value : Nat) : Bool :=` — Begins definition `evenParityLowByte`; `:=` ends the signature and the indented body follows.

**L173** `  let count := (List.range 8).foldl` — Binds immutable local `count` to `(List.range 8).foldl`.

**L174** `    (fun total index => total + if Nat.testBit value index then 1 else 0) 0` — Continues the typed parameter/signature for subtraction flags.

**L175** `  count % 2 == 0` — Returns true when the low-byte set-bit count is even.

**L177** `def subtractionFlags (width : OperandWidth) (minuend subtrahend : Nat) : StatusFlags :=` — Begins definition `subtractionFlags`; `:=` ends the signature and the indented body follows.

**L178** `  let result := (minuend + modulus width - subtrahend) % modulus width` — Binds immutable local `result` to `(minuend + modulus width - subtrahend) % modulus width`.

**L179** `  let minuendSign := signBit width minuend` — Binds immutable local `minuendSign` to `signBit width minuend`.

**L180** `  let subtrahendSign := signBit width subtrahend` — Binds immutable local `subtrahendSign` to `signBit width subtrahend`.

**L181** `  let resultSign := signBit width result` — Binds immutable local `resultSign` to `signBit width result`.

**L182** `  {` — Opens a record literal; following lines assign its fields.

**L183** `    cf := decide (minuend < subtrahend)` — Assigns record field/local component `cf` the value `decide (minuend < subtrahend)`.

**L184** `    of := (minuendSign != subtrahendSign) && (resultSign != minuendSign)` — Assigns record field/local component `of` the value `(minuendSign != subtrahendSign) && (resultSign != minuendSign)`.

**L185** `    sf := resultSign` — Assigns record field/local component `sf` the value `resultSign`.

**L186** `    zf := result == 0` — Assigns record field/local component `zf` the value `result == 0`.

**L187** `    af := decide (minuend % 16 < subtrahend % 16)` — Assigns record field/local component `af` the value `decide (minuend % 16 < subtrahend % 16)`.

**L188** `    pf := evenParityLowByte result` — Assigns record field/local component `pf` the value `evenParityLowByte result`.

**L189** `  }` — Closes the record literal.

**L191** `def CMP (instruction : CmpInstruction) : Option ComparisonResult :=` — Begins definition `CMP`; `:=` ends the signature and the indented body follows.

**L192** `  match operationWidth instruction.encoding with` — Starts pattern matching; one following constructor branch will be selected.

**L193** `  | none => none` — Match branch: input pattern `none` produces/evaluates `none`.

**L194** `  | some width =>` — Match branch: input pattern `some width` produces/evaluates ``.

**L195** `      let first := firstOperand instruction.operands` — Binds immutable local `first` to `firstOperand instruction.operands`.

**L196** `      if first.value.width != width || !locationsAllowed instruction.operands ||` — Tests condition `first.value.width != width || !locationsAllowed instruction.operands ||`; following code is its true branch.

**L197** `          !registersAllowed instruction.encoding instruction.operands then` — Adds unavailable registers to the rejection condition and opens its true branch.

**L198** `        none` — Returns `Option.none`, meaning the modeled operation is invalid or unavailable.

**L199** `      else` — Starts the false branch of the preceding conditional.

**L200** `        match secondOperandValue width instruction.operands with` — Starts pattern matching; one following constructor branch will be selected.

**L201** `        | none => none` — Match branch: input pattern `none` produces/evaluates `none`.

**L202** `        | some second =>` — Match branch: input pattern `some second` produces/evaluates ``.

**L203** `            let firstValue := first.value.bits.toNat` — Binds immutable local `firstValue` to `first.value.bits.toNat`.

**L204** `            let result := (firstValue + modulus width - second) % modulus width` — Binds immutable local `result` to `(firstValue + modulus width - second) % modulus width`.

**L205** `            some {` — Wraps `{` in successful `Option.some`.

**L206** `              temp := { width := width, bits := BitVec.ofNat width.bitCount result }` — Assigns record field/local component `temp` the value `{ width := width, bits := BitVec.ofNat width.bitCount result }`.

**L207** `              flags := subtractionFlags width firstValue second` — Assigns record field/local component `flags` the value `subtractionFlags width firstValue second`.

**L208** `            }` — Closes the record literal.

**L210** `def execCMP (instruction : CmpInstruction) (state : MachineState) : Option MachineState :=` — Begins definition `execCMP`; `:=` ends the signature and the indented body follows.

**L211** `  match CMP instruction with` — Starts pattern matching; one following constructor branch will be selected.

**L212** `  | none => none` — Match branch: input pattern `none` produces/evaluates `none`.

**L213** `  | some comparison => some { state with flags := comparison.flags }` — Match branch: input pattern `some comparison` produces/evaluates `some { state with flags := comparison.flags }`.

**L215** `end Spec2Lean.X86.OperandComparison` — Closes namespace `Spec2Lean.X86.OperandComparison`.

## 4. BitwiseOperators.lean — SystemVerilog bitwise operators

Source: `translations/systemverilog/1800-2023/plan:9c9969edb45332737eb371fd/BitwiseOperators/BitwiseOperators.lean`

**L1** `import Std` — Imports Lean's standard library.

**L3** `namespace Spec2Lean.Systemverilog.BitwiseOperators` — Opens namespace `Spec2Lean.Systemverilog.BitwiseOperators`; following names receive this prefix.

**L5** `inductive FourStateBit where` — Begins closed datatype `FourStateBit`; following lines list its constructors.

**L6** `  | zero` — Declares constructor `zero` of the datatype currently being defined.

**L7** `  | one` — Declares constructor `one` of the datatype currently being defined.

**L8** `  | x` — Declares constructor `x` of the datatype currently being defined.

**L9** `  | z` — Declares constructor `z` of the datatype currently being defined.

**L10** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L12** `inductive Signedness where` — Begins closed datatype `Signedness`; following lines list its constructors.

**L13** `  | unsigned` — Declares constructor `unsigned` of the datatype currently being defined.

**L14** `  | signed` — Declares constructor `signed` of the datatype currently being defined.

**L15** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L17** `/-- Bits are stored least-significant first. -/` — Documentation comment: the following representation stores the least-significant bit first.

**L18** `structure IntegralValue where` — Begins record type `IntegralValue`; following lines list its fields.

**L19** `  bits : List FourStateBit` — Declares field/parameter `bits` with type `List FourStateBit`.

**L20** `  signedness : Signedness` — Declares field/parameter `signedness` with type `Signedness`.

**L21** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L23** `structure BinaryOperands where` — Begins record type `BinaryOperands`; following lines list its fields.

**L24** `  lhs : List FourStateBit` — Declares field/parameter `lhs` with type `List FourStateBit`.

**L25** `  rhs : List FourStateBit` — Declares field/parameter `rhs` with type `List FourStateBit`.

**L26** `  resultSignedness : Signedness` — Declares field/parameter `resultSignedness` with type `Signedness`.

**L27** `  deriving DecidableEq, Repr` — Generates equality decision and printable-representation support for the type above.

**L29** `def mostSignificantBit (bits : List FourStateBit) : FourStateBit :=` — Begins definition `mostSignificantBit`; `:=` ends the signature and the indented body follows.

**L30** `  match bits.reverse with` — Starts pattern matching; one following constructor branch will be selected.

**L31** `  | [] => .zero` — Match branch: input pattern `[]` produces/evaluates `.zero`.

**L32** `  | bit :: _ => bit` — Match branch: input pattern `bit :: _` produces/evaluates `bit`.

**L34** `def extendBits (bits : List FourStateBit) (width : Nat)` — Begins function `extendBits`; its signature/body continues below.

**L35** `    (signExtend : Bool) : List FourStateBit :=` — Finishes the multiline function signature and starts its body after `:=`.

**L36** `  if width <= bits.length then` — Tests condition `width <= bits.length`; following code is its true branch.

**L37** `    bits.take width` — Returns the requested number of low bits when truncation/no extension is needed.

**L38** `  else` — Starts the false branch of the preceding conditional.

**L39** `    let fill := if signExtend then mostSignificantBit bits else .zero` — Binds immutable local `fill` to `if signExtend then mostSignificantBit bits else .zero`.

**L40** `    bits ++ List.replicate (width - bits.length) fill` — Appends enough fill bits to reach the requested width.

**L42** `def binaryResultSignedness (lhs rhs : IntegralValue) : Signedness :=` — Begins definition `binaryResultSignedness`; `:=` ends the signature and the indented body follows.

**L43** `  match lhs.signedness, rhs.signedness with` — Starts pattern matching; one following constructor branch will be selected.

**L44** `  | .signed, .signed => .signed` — Match branch: input pattern `.signed, .signed` produces/evaluates `.signed`.

**L45** `  | _, _ => .unsigned` — Match branch: input pattern `_, _` produces/evaluates `.unsigned`.

**L47** `def normalizeBinaryOperands (lhs rhs : IntegralValue) : BinaryOperands :=` — Begins definition `normalizeBinaryOperands`; `:=` ends the signature and the indented body follows.

**L48** `  let width := max lhs.bits.length rhs.bits.length` — Binds immutable local `width` to `max lhs.bits.length rhs.bits.length`.

**L49** `  let resultSignedness := binaryResultSignedness lhs rhs` — Binds immutable local `resultSignedness` to `binaryResultSignedness lhs rhs`.

**L50** `  let signExtend := resultSignedness == .signed` — Binds immutable local `signExtend` to `resultSignedness == .signed`.

**L51** `  {` — Opens a record literal; following lines assign its fields.

**L52** `    lhs := extendBits lhs.bits width signExtend` — Assigns record field/local component `lhs` the value `extendBits lhs.bits width signExtend`.

**L53** `    rhs := extendBits rhs.bits width signExtend` — Assigns record field/local component `rhs` the value `extendBits rhs.bits width signExtend`.

**L54** `    resultSignedness := resultSignedness` — Assigns record field/local component `resultSignedness` the value `resultSignedness`.

**L55** `  }` — Closes the record literal.

**L57** `def andBit (a b : FourStateBit) : FourStateBit :=` — Begins definition `andBit`; `:=` ends the signature and the indented body follows.

**L58** `  match a, b with` — Starts pattern matching; one following constructor branch will be selected.

**L59** `  | .zero, _ | _, .zero => .zero` — Match branch: input pattern `.zero, _ | _, .zero` produces/evaluates `.zero`.

**L60** `  | .one, .one => .one` — Match branch: input pattern `.one, .one` produces/evaluates `.one`.

**L61** `  | _, _ => .x` — Match branch: input pattern `_, _` produces/evaluates `.x`.

**L63** `def orBit (a b : FourStateBit) : FourStateBit :=` — Begins definition `orBit`; `:=` ends the signature and the indented body follows.

**L64** `  match a, b with` — Starts pattern matching; one following constructor branch will be selected.

**L65** `  | .one, _ | _, .one => .one` — Match branch: input pattern `.one, _ | _, .one` produces/evaluates `.one`.

**L66** `  | .zero, .zero => .zero` — Match branch: input pattern `.zero, .zero` produces/evaluates `.zero`.

**L67** `  | _, _ => .x` — Match branch: input pattern `_, _` produces/evaluates `.x`.

**L69** `def xorBit (a b : FourStateBit) : FourStateBit :=` — Begins definition `xorBit`; `:=` ends the signature and the indented body follows.

**L70** `  match a, b with` — Starts pattern matching; one following constructor branch will be selected.

**L71** `  | .zero, .zero | .one, .one => .zero` — Match branch: input pattern `.zero, .zero | .one, .one` produces/evaluates `.zero`.

**L72** `  | .zero, .one | .one, .zero => .one` — Match branch: input pattern `.zero, .one | .one, .zero` produces/evaluates `.one`.

**L73** `  | _, _ => .x` — Match branch: input pattern `_, _` produces/evaluates `.x`.

**L75** `def xnorBit (a b : FourStateBit) : FourStateBit :=` — Begins definition `xnorBit`; `:=` ends the signature and the indented body follows.

**L76** `  match a, b with` — Starts pattern matching; one following constructor branch will be selected.

**L77** `  | .zero, .zero | .one, .one => .one` — Match branch: input pattern `.zero, .zero | .one, .one` produces/evaluates `.one`.

**L78** `  | .zero, .one | .one, .zero => .zero` — Match branch: input pattern `.zero, .one | .one, .zero` produces/evaluates `.zero`.

**L79** `  | _, _ => .x` — Match branch: input pattern `_, _` produces/evaluates `.x`.

**L81** `def notBit (a : FourStateBit) : FourStateBit :=` — Begins definition `notBit`; `:=` ends the signature and the indented body follows.

**L82** `  match a with` — Starts pattern matching; one following constructor branch will be selected.

**L83** `  | .zero => .one` — Match branch: input pattern `.zero` produces/evaluates `.one`.

**L84** `  | .one => .zero` — Match branch: input pattern `.one` produces/evaluates `.zero`.

**L85** `  | .x | .z => .x` — Match branch: input pattern `.x | .z` produces/evaluates `.x`.

**L87** `def applyBinary (bitOp : FourStateBit -> FourStateBit -> FourStateBit)` — Begins function `applyBinary`; its signature/body continues below.

**L88** `    (lhs rhs : IntegralValue) : IntegralValue :=` — Finishes the multiline function signature and starts its body after `:=`.

**L89** `  let operands := normalizeBinaryOperands lhs rhs` — Binds immutable local `operands` to `normalizeBinaryOperands lhs rhs`.

**L90** `  {` — Opens a record literal; following lines assign its fields.

**L91** `    bits := List.zipWith bitOp operands.lhs operands.rhs` — Assigns record field/local component `bits` the value `List.zipWith bitOp operands.lhs operands.rhs`.

**L92** `    signedness := operands.resultSignedness` — Assigns record field/local component `signedness` the value `operands.resultSignedness`.

**L93** `  }` — Closes the record literal.

**L95** `def bitwiseAnd (lhs rhs : IntegralValue) : IntegralValue :=` — Begins definition `bitwiseAnd`; `:=` ends the signature and the indented body follows.

**L96** `  applyBinary andBit lhs rhs` — Normalizes both operands and applies four-state AND at every bit position.

**L98** `def bitwiseOr (lhs rhs : IntegralValue) : IntegralValue :=` — Begins definition `bitwiseOr`; `:=` ends the signature and the indented body follows.

**L99** `  applyBinary orBit lhs rhs` — Normalizes both operands and applies four-state OR at every bit position.

**L101** `def bitwiseXor (lhs rhs : IntegralValue) : IntegralValue :=` — Begins definition `bitwiseXor`; `:=` ends the signature and the indented body follows.

**L102** `  applyBinary xorBit lhs rhs` — Normalizes both operands and applies four-state XOR at every bit position.

**L104** `def bitwiseXnorCaretTilde (lhs rhs : IntegralValue) : IntegralValue :=` — Begins definition `bitwiseXnorCaretTilde`; `:=` ends the signature and the indented body follows.

**L105** `  applyBinary xnorBit lhs rhs` — Normalizes both operands and applies four-state XNOR at every bit position.

**L107** `def bitwiseXnorTildeCaret (lhs rhs : IntegralValue) : IntegralValue :=` — Begins definition `bitwiseXnorTildeCaret`; `:=` ends the signature and the indented body follows.

**L108** `  applyBinary xnorBit lhs rhs` — Normalizes both operands and applies four-state XNOR at every bit position.

**L110** `def bitwiseNot (operand : IntegralValue) : IntegralValue :=` — Begins definition `bitwiseNot`; `:=` ends the signature and the indented body follows.

**L111** `  {` — Opens a record literal; following lines assign its fields.

**L112** `    bits := operand.bits.map notBit` — Assigns record field/local component `bits` the value `operand.bits.map notBit`.

**L113** `    signedness := operand.signedness` — Assigns record field/local component `signedness` the value `operand.signedness`.

**L114** `  }` — Closes the record literal.

**L116** `end Spec2Lean.Systemverilog.BitwiseOperators` — Closes namespace `Spec2Lean.Systemverilog.BitwiseOperators`.
