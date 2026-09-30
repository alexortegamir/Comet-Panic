' COMET PANIC - arcade shooter for the ZX Spectrum 48K.
' Boriel ZX Basic source; build with: python3 build_comet_panic_tap.py
' Controls: O = left, P = right, SPACE = fire.
'
' Speed notes: sprites, stars and sound are assembler; the hot game state lives in
' fixed memory tables read with PEEK/POKE (much faster than Boriel arrays).

#include "sprites.bas"

const PLAYERY as ubyte = 166
const OBJSHOT as ubyte = 1
const OBJBOMB as ubyte = 3
const OBJENEMY as ubyte = 6
const NOBJ as ubyte = 13

' Runtime tables (above the compiled code, below the UDGs)
const OBJT as uinteger = 61440   ' 14 objects x 6: drawn, x, y, rows, frame address
const STARS as uinteger = 61536  ' 16 stars x 3: x, y, speed
const ENEM as uinteger = 61600   ' 8 enemies x 16: state, timer, x, y, vx, vy, slot x, slot y
const SHOTS as uinteger = 61760  ' 2 shots x 3: active, x, y
const BOMBS as uinteger = 61776  ' 3 bombs x 3: active, x, y
const FADDR as uinteger = 61800  ' address of each preshifted sprite frame

' Parameters for the assembler routines, in the (unused) printer buffer
dim sx as ubyte at 23296
dim sy as ubyte at 23297
dim sh as ubyte at 23298
dim scol as ubyte at 23299
dim sf as uinteger at 23300
dim sndlen as ubyte at 23302
dim sndper as ubyte at 23303
dim obj as ubyte at 23304

dim seed as uinteger = 12345
dim px, lives, wave, wtype, fc, ft, lastf, firecool, dead as ubyte
dim score, hiscore as uinteger
dim fcx, fcy as integer
dim pending, alive, attackers, spawnt as ubyte
dim acc, vm, vd as integer
dim maxatt, attch, bombch, ecol, eframe, epts as ubyte
dim orbXBase, orbYBase, swayXBase, swayYBase as uinteger

' Flock slots relative to its centre (1/16 pixel units)
dim slotX(7) as integer => {-768, -256, 256, 768, -512, 0, 512, 0}
dim slotY(7) as integer => {0, 0, 0, 0, 384, 384, 384, 768}

' Per enemy type: Cold Eye, Super Fly, Atomic
dim accT(2) as ubyte => {5, 9, 7}
dim vmT(2) as ubyte => {40, 60, 50}
dim vdT(2) as ubyte => {56, 80, 66}
dim colT(2) as ubyte => {69, 68, 67}
dim ptsT(2) as ubyte => {3, 5, 8}

' ---------------------------------------------------------------- assembler library

asm
    jp cpEnd

; C = x, B = y -> HL = screen address (B, C preserved)
cpScrAddr:
    ld a,b
    and 7
    ld h,a
    ld a,b
    rra
    rra
    rra
    and 18h
    or h
    or 40h
    ld h,a
    ld a,b
    rla
    rla
    and 0E0h
    ld l,a
    ld a,c
    rra
    rra
    rra
    and 1Fh
    or l
    ld l,a
    ret

; XOR a preshifted sprite: C = x, B = y, A = rows, DE = frame
cpSprXor:
    push af
    call cpScrAddr
    ld a,c
    and 7
    jr z,cpSxGo
    push hl
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld b,h
    ld c,l
    add hl,hl
    add hl,bc
    add hl,de
    ex de,hl
    pop hl
cpSxGo:
    pop af
    ld b,a
cpSxRow:
    ld a,(de)
    xor (hl)
    ld (hl),a
    inc de
    inc l
    ld a,(de)
    xor (hl)
    ld (hl),a
    inc de
    inc l
    ld a,(de)
    xor (hl)
    ld (hl),a
    inc de
    dec l
    dec l
    inc h
    ld a,h
    and 7
    jr nz,cpSxNext
    ld a,l
    add a,32
    ld l,a
    jr c,cpSxNext
    ld a,h
    sub 8
    ld h,a
cpSxNext:
    djnz cpSxRow
    ret

; Colour the cells under the sprite described by sx, sy, sh, scol
cpPaint:
    ld a,(23297)
    ld c,a
    rrca
    rrca
    rrca
    and 1Fh
    ld l,a
    ld h,0
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    add hl,hl
    ld a,(23296)
    rrca
    rrca
    rrca
    and 1Fh
    or l
    ld l,a
    ld de,5800h
    add hl,de
    ld a,(23298)
    dec a
    add a,c
    rrca
    rrca
    rrca
    and 1Fh
    ld b,a
    ld a,c
    rrca
    rrca
    rrca
    and 1Fh
    ld c,a
    ld a,b
    sub c
    inc a
    ld b,a
    ld a,(23299)
    ld de,30
cpPsRow:
    ld (hl),a
    inc hl
    ld (hl),a
    inc hl
    ld (hl),a
    add hl,de
    djnz cpPsRow
    ret

; XOR one pixel: C = x, B = y
cpPixXor:
    call cpScrAddr
    ld a,c
    and 7
    ld b,a
    ld a,80h
    jr z,cpPxDone
cpPxLoop:
    rrca
    djnz cpPxLoop
cpPxDone:
    xor (hl)
    ld (hl),a
    ret

; HL = record of object (obj)
cpObjRec:
    ld a,(23304)
    ld l,a
    add a,a
    add a,l
    add a,a
    ld l,a
    ld h,0
    ld de,61440
    add hl,de
    ret

; Erase the object at HL if it is drawn (HL preserved)
cpObjErase:
    ld a,(hl)
    or a
    ret z
    ld (hl),0
    push hl
    inc hl
    ld c,(hl)
    inc hl
    ld b,(hl)
    inc hl
    ld a,(hl)
    inc hl
    ld e,(hl)
    inc hl
    ld d,(hl)
    call cpSprXor
    pop hl
    ret

cpEnd:
end asm

' Move object obj to (sx, sy) with frame sf, sh rows, colour scol
sub putObj()
    asm
    call cpObjRec
    call cpObjErase
    push hl
    ld a,(23296)
    ld c,a
    ld a,(23297)
    ld b,a
    ld de,(23300)
    ld a,(23298)
    call cpSprXor
    call cpPaint
    pop hl
    ld (hl),1
    inc hl
    ld a,(23296)
    ld (hl),a
    inc hl
    ld a,(23297)
    ld (hl),a
    inc hl
    ld a,(23298)
    ld (hl),a
    inc hl
    ld de,(23300)
    ld (hl),e
    inc hl
    ld (hl),d
    end asm
end sub

sub hideObj()
    asm
    call cpObjRec
    call cpObjErase
    end asm
end sub

sub moveStars()
    asm
    ld hl,61536
    ld b,16
cpMsLoop:
    push bc
    push hl
    ld c,(hl)
    inc hl
    ld b,(hl)
    call cpPixXor
    pop hl
    push hl
    inc hl
    ld a,(hl)
    inc hl
    add a,(hl)
    dec hl
    cp 184
    jr c,cpMsKeep
    ld a,r
    ld c,a
    ld a,(23672)
    rlca
    add a,c
    dec hl
    ld (hl),a
    inc hl
    ld a,16
cpMsKeep:
    ld (hl),a
    ld b,a
    dec hl
    ld c,(hl)
    call cpPixXor
    pop hl
    inc hl
    inc hl
    inc hl
    pop bc
    djnz cpMsLoop
    end asm
end sub

sub toggleStars()
    asm
    ld hl,61536
    ld b,16
cpTsLoop:
    push bc
    push hl
    ld c,(hl)
    inc hl
    ld b,(hl)
    call cpPixXor
    pop hl
    inc hl
    inc hl
    inc hl
    pop bc
    djnz cpTsLoop
    end asm
end sub

' Square wave: sndlen half-cycles of sndper delay
sub tone()
    asm
    ld a,(23302)
    ld b,a
    xor a
cpTnLoop:
    xor 10h
    out (0FEh),a
    ld c,a
    ld a,(23303)
cpTnDelay:
    dec a
    jr nz,cpTnDelay
    ld a,c
    djnz cpTnLoop
    xor a
    out (0FEh),a
    end asm
end sub

' Noise read from the ROM
sub noise()
    asm
    ld hl,(_seed)
    ld a,h
    and 3Fh
    ld h,a
    ld a,(23302)
    ld b,a
cpNzLoop:
    ld a,(hl)
    and 10h
    out (0FEh),a
    inc hl
    ld a,(23303)
cpNzDelay:
    dec a
    jr nz,cpNzDelay
    djnz cpNzLoop
    xor a
    out (0FEh),a
    end asm
end sub

' ---------------------------------------------------------------- helpers

function rnd8() as ubyte
    seed = seed bXOR (seed << 7)
    seed = seed bXOR (seed >> 9)
    seed = seed bXOR (seed << 8)
    return seed bAND 255
end function

' Wait so the game runs at a steady 25 frames per second
sub syncFrame()
    dim d as ubyte
    do
        d = peek(23672) - lastf
        if d >= 2 then exit do
        asm
        halt
        end asm
    loop
    lastf = peek(23672)
end sub

sub waitFrames(n as ubyte)
    dim i as ubyte
    for i = 1 to n
        syncFrame()
    next i
end sub

sub drawObj(o as ubyte, x as ubyte, y as ubyte, f as ubyte, h as ubyte, c as ubyte)
    obj = o
    sx = x
    sy = y
    sh = h
    sf = peek(uinteger, FADDR + (cast(uinteger, f) << 1))
    scol = c
    putObj()
end sub

sub hideAll()
    for obj = 0 to NOBJ
        hideObj()
    next obj
end sub

sub clearObjects()
    dim a as uinteger
    for a = OBJT to OBJT + 6 * NOBJ step 6
        poke a, 0
    next a
end sub

sub initStars()
    dim a as uinteger
    for a = STARS to STARS + 45 step 3
        poke a, rnd8()
        poke a + 1, 16 + (rnd8() bAND 127) + (rnd8() bAND 31)
        poke a + 2, 1 + (rnd8() bAND 3)
    next a
    toggleStars()
end sub

sub drawGround()
    dim l, c, v as ubyte
    dim a as uinteger
    for l = 0 to 7
        if l = 0 then
            v = 255
        elseif l = 1 then
            v = 221
        elseif l = 2 then
            v = 119
        elseif l = 4 then
            v = 34
        elseif l = 6 then
            v = 136
        else
            v = 0
        end if
        a = 20704 + cast(uinteger, l) * 256
        for c = 0 to 31
            poke a + c, v
        next c
    next l
    for c = 0 to 31
        poke 23264 + c, 66
    next c
end sub

sub printScore()
    print at 0, 7; ink 7; bright 1; score; "0"
end sub

sub printHud()
    print at 0, 0; ink 5; bright 1; "PUNTOS"; at 0, 20; "MAXIMO"
    print at 0, 27; ink 6; bright 1; hiscore; "0"
    print at 1, 0; ink 4; bright 1; "OLEADA "; wave; " "
    print at 1, 24; ink 7; bright 1; "VIDAS "; lives
    printScore()
end sub

' Centered one-line message; stars are hidden while it is shown
sub message(row as ubyte, text as string, col as ubyte, frames as ubyte)
    toggleStars()
    print at row, (32 - len(text)) >> 1; ink col; bright 1; text
    waitFrames(frames)
    print at row, 0; "                                "
    toggleStars()
end sub

' ---------------------------------------------------------------- game

sub startWave()
    dim lvl, i as ubyte
    dim e as uinteger
    wtype = (wave - 1) mod 3
    lvl = (wave - 1) / 3
    acc = accT(wtype) + lvl
    vm = vmT(wtype) + lvl * 6
    vd = vdT(wtype) + lvl * 8
    maxatt = 2 + lvl
    if maxatt > 5 then maxatt = 5
    attch = 8 + wave * 3
    bombch = 10 + wave * 3
    ecol = colT(wtype)
    eframe = SPR_COLDEYE + (wtype << 1)
    epts = ptsT(wtype)
    e = ENEM
    for i = 0 to 7
        poke e, 0
        poke integer e + 10, slotX(i)
        poke integer e + 12, slotY(i)
        e = e + 16
    next i
    pending = 16
    alive = 0
    attackers = 0
    spawnt = 10
    printHud()
    drawObj(0, px, PLAYERY, SPR_SHIP, 16, 71)
    if wtype = 0 then
        message(11, "OLEADA " + str(wave) + ": COLD EYE", 5, 50)
    elseif wtype = 1 then
        message(11, "OLEADA " + str(wave) + ": SUPER FLY", 4, 50)
    else
        message(11, "OLEADA " + str(wave) + ": ATOMIC", 3, 50)
    end if
end sub

sub killEnemy(e as uinteger)
    if peek(e) = 2 then
        attackers = attackers - 1
        score = score + epts * 2
    else
        score = score + epts
    end if
    poke e, 3
    poke e + 1, 10
    printScore()
    sndlen = 60
    sndper = 6
    noise()
end sub

sub checkShotHit(s as ubyte, a as uinteger)
    dim j, st as ubyte
    dim e as uinteger
    dim cx, cy, exx, eyy as integer
    cx = cast(integer, peek(a + 1)) + 8
    cy = peek(a + 2)
    e = ENEM
    for j = 0 to 7
        st = peek(e)
        if st = 1 or st = 2 then
            exx = peek(integer, e + 2) >> 4
            eyy = peek(integer, e + 4) >> 4
            if cx > exx and cx < exx + 16 and cy < eyy + 13 and cy + 8 > eyy then
                killEnemy(e)
                poke a, 0
                obj = OBJSHOT + s
                hideObj()
                return
            end if
        end if
        e = e + 16
    next j
end sub

sub updatePlayer()
    dim k, i as ubyte
    dim a as uinteger
    k = in(57342)
    if (k bAND 2) = 0 and px > 4 then px = px - 4
    if (k bAND 1) = 0 and px < 232 then px = px + 4
    obj = 0
    sx = px
    sy = PLAYERY
    sh = 16
    sf = peek(uinteger, FADDR + ((SPR_SHIP + ((fc >> 1) bAND 1)) << 1))
    scol = 71
    putObj()
    if firecool then
        firecool = firecool - 1
    elseif (in(32766) bAND 1) = 0 then
        a = SHOTS
        for i = 0 to 1
            if peek(a) = 0 then
                poke a, 1
                poke a + 1, px
                poke a + 2, PLAYERY - 4
                firecool = 4
                sndlen = 16
                sndper = 20
                tone()
                exit for
            end if
            a = a + 3
        next i
    end if
end sub

sub updateShots()
    dim i, y as ubyte
    dim a as uinteger
    a = SHOTS
    for i = 0 to 1
        if peek(a) then
            obj = OBJSHOT + i
            y = peek(a + 2)
            if y < 26 then
                poke a, 0
                hideObj()
            else
                y = y - 10
                poke a + 2, y
                sx = peek(a + 1)
                sy = y
                sh = 8
                sf = peek(uinteger, FADDR + (SPR_SHOT << 1))
                scol = 70
                putObj()
                checkShotHit(i, a)
            end if
        end if
        a = a + 3
    next i
end sub

sub dropBomb(x as ubyte, y as ubyte)
    dim a as uinteger
    for a = BOMBS to BOMBS + 6 step 3
        if peek(a) = 0 then
            poke a, 1
            poke a + 1, x
            poke a + 2, y
            return
        end if
    next a
end sub

sub updateBombs()
    dim i, y as ubyte
    dim a as uinteger
    dim d as integer
    a = BOMBS
    for i = 0 to 2
        if peek(a) then
            obj = OBJBOMB + i
            y = peek(a + 2) + 5
            if y > 176 then
                poke a, 0
                hideObj()
            else
                poke a + 2, y
                sx = peek(a + 1)
                sy = y
                sh = 6
                sf = peek(uinteger, FADDR + (SPR_BOMB << 1))
                scol = 66
                putObj()
                if y > PLAYERY - 3 and y < PLAYERY + 12 then
                    d = cast(integer, sx) - cast(integer, px)
                    if d > -7 and d < 7 then dead = 1
                end if
            end if
        end if
        a = a + 3
    next i
end sub

' The flock centre sways across the screen
sub updateFormation()
    ft = ft + 1
    fcx = peek(integer, swayXBase + (((ft >> 1) bAND 63) << 1))
    fcy = peek(integer, swayYBase + ((ft bAND 63) << 1))
end sub

sub maybeAttack()
    dim e as uinteger
    if attackers < maxatt then
        if rnd8() < attch then
            e = ENEM + (cast(uinteger, rnd8() bAND 7) << 4)
            if peek(e) = 1 and peek(integer, e + 4) < 1600 then
                poke e, 2
                poke integer e + 8, -40
                attackers = attackers + 1
                sndlen = 30
                sndper = 40
                tone()
            end if
        end if
    end if
end sub

sub spawnEnemies()
    dim e as uinteger
    if pending = 0 then return
    if spawnt then
        spawnt = spawnt - 1
        return
    end if
    for e = ENEM to ENEM + 112 step 16
        if peek(e) = 0 then
            poke e, 1
            poke integer e + 4, cast(integer, 24 + (rnd8() bAND 63)) << 4
            poke integer e + 8, -16
            if rnd8() bAND 1 then
                poke integer e + 2, 0
                poke integer e + 6, 64
            else
                poke integer e + 2, 3824
                poke integer e + 6, -64
            end if
            pending = pending - 1
            alive = alive + 1
            spawnt = 6
            return
        end if
    next e
end sub

sub updateEnemies()
    dim i, st, t as ubyte
    dim e as uinteger
    dim x, y, vx, vy, tx, ty, d as integer
    e = ENEM
    for i = 0 to 7
        st = peek(e)
        obj = OBJENEMY + i
        if st = 3 then
            t = peek(e + 1) - 1
            poke e + 1, t
            if t = 0 then
                hideObj()
                poke e, 0
                alive = alive - 1
            else
                sx = peek(integer, e + 2) >> 4
                sy = peek(integer, e + 4) >> 4
                sh = 16
                sf = peek(uinteger, FADDR + ((SPR_EXPL + ((t >> 1) bAND 1)) << 1))
                scol = 70
                putObj()
            end if
        elseif st then
            x = peek(integer, e + 2)
            y = peek(integer, e + 4)
            vx = peek(integer, e + 6)
            vy = peek(integer, e + 8)
            if st = 1 then
                t = ((ft + (i << 3)) bAND 63) << 1
                tx = fcx + peek(integer, e + 10) + peek(integer, orbXBase + t)
                ty = fcy + peek(integer, e + 12) + peek(integer, orbYBase + t)
            else
                tx = cast(integer, px) << 4
                ty = 3400
            end if
            if tx > x then
                vx = vx + acc
            else
                vx = vx - acc
            end if
            if ty > y then
                vy = vy + acc
            else
                vy = vy - acc
            end if
            if vx > vm then vx = vm
            if vx < -vm then vx = -vm
            if st = 1 then
                if vx > 0 then
                    vx = vx - 1
                elseif vx < 0 then
                    vx = vx + 1
                end if
                if vy > vm then vy = vm
                if vy < -vm then vy = -vm
            else
                if vy > vd then vy = vd
                if vy < -vd then vy = -vd
            end if
            x = x + vx
            y = y + vy
            if x < 0 then
                x = 0
                vx = -vx
            elseif x > 3824 then
                x = 3824
                vx = -vx
            end if
            if y < 256 then
                y = 256
                vy = 0
            elseif y > 2720 then
                if st = 2 then
                    ' Dived past the player: reappear at the top and rejoin the flock
                    hideObj()
                    y = 256
                    vy = 16
                    x = cast(integer, 16 + (rnd8() bAND 127) + (rnd8() bAND 63)) << 4
                    st = 1
                    poke e, 1
                    attackers = attackers - 1
                else
                    y = 2720
                    vy = 0
                end if
            end if
            poke integer e + 2, x
            poke integer e + 4, y
            poke integer e + 6, vx
            poke integer e + 8, vy
            sx = x >> 4
            sy = y >> 4
            sh = 16
            sf = peek(uinteger, FADDR + ((eframe + (((fc >> 2) + i) bAND 1)) << 1))
            scol = ecol
            putObj()
            if sy > PLAYERY - 12 then
                d = cast(integer, sx) - cast(integer, px)
                if d > -12 and d < 12 then dead = 1
            end if
            if st = 2 and sy < 140 then
                if rnd8() < bombch then
                    d = cast(integer, sx) - cast(integer, px)
                    if d > -48 and d < 48 then dropBomb(sx, sy + 12)
                end if
            end if
        end if
        e = e + 16
    next i
end sub

sub resetShotsAndBombs()
    dim a as uinteger
    for a = SHOTS to BOMBS + 6 step 3
        poke a, 0
    next a
end sub

sub playerDeath()
    dim n, st as ubyte
    dim e as uinteger
    for n = 0 to 24
        syncFrame()
        moveStars()
        if n bAND 2 then
            drawObj(0, px, PLAYERY, SPR_EXPL + ((n >> 2) bAND 1), 16, 70)
        else
            drawObj(0, px, PLAYERY, SPR_EXPL + ((n >> 2) bAND 1), 16, 66)
        end if
        sndlen = 40
        sndper = 10 + n
        noise()
    next n
    hideAll()
    for e = ENEM to ENEM + 112 step 16
        st = peek(e)
        if st = 1 or st = 2 then pending = pending + 1
        poke e, 0
    next e
    resetShotsAndBombs()
    alive = 0
    attackers = 0
    dead = 0
    spawnt = 25
    lives = lives - 1
    px = 120
    printHud()
    if lives then waitFrames(25)
end sub

sub waveCleared()
    dim n as ubyte
    hideAll()
    resetShotsAndBombs()
    score = score + 10 * cast(uinteger, wave)
    printScore()
    for n = 0 to 6
        sndlen = 40
        sndper = 60 - n * 7
        tone()
    next n
    message(11, "OLEADA SUPERADA  +" + str(cast(uinteger, wave) * 100), 6, 60)
    wave = wave + 1
    startWave()
end sub

sub playGame()
    dim n as ubyte
    border 0
    paper 0
    ink 7
    bright 1
    flash 0
    cls
    drawGround()
    clearObjects()
    initStars()
    resetShotsAndBombs()
    score = 0
    lives = 3
    wave = 1
    px = 120
    dead = 0
    firecool = 0
    lastf = peek(23672)
    startWave()
    do
        syncFrame()
        fc = fc + 1
        moveStars()
        updatePlayer()
        updateShots()
        updateFormation()
        updateEnemies()
        updateBombs()
        maybeAttack()
        spawnEnemies()
        if dead then
            playerDeath()
            if lives = 0 then exit do
        elseif pending = 0 and alive = 0 then
            waveCleared()
        end if
    loop
    if score > hiscore then hiscore = score
    toggleStars()
    print at 11, 8; ink 2; bright 1; flash 1; " FIN DEL JUEGO "
    for n = 0 to 12
        sndlen = 50
        sndper = 40 + n * 12
        tone()
    next n
    waitFrames(120)
end sub

sub drawLogo()
    dim r, c, y as ubyte
    dim a, s as uinteger
    s = @titleGfx(0)
    for r = 0 to 23
        y = 16 + r
        a = 16389 + (cast(uinteger, y bAND 192) << 5) + (cast(uinteger, y bAND 7) << 8) + (cast(uinteger, y bAND 56) << 2)
        for c = 0 to 21
            poke a + c, peek(s)
            s = s + 1
        next c
    next r
    for c = 5 to 26
        poke 22592 + c, 70
        poke 22624 + c, 66
        poke 22656 + c, 67
    next c
end sub

sub titleScreen()
    dim n, pressed as ubyte
    border 0
    paper 0
    ink 7
    bright 1
    flash 0
    cls
    drawGround()
    clearObjects()
    drawLogo()
    print at 6, 9; ink 5; bright 1; "by AlexOrtega"
    print at 13, 7; ink 5; bright 0; "30"; at 13, 15; ink 4; "50"; at 13, 23; ink 3; "80"
    print at 17, 2; ink 7; bright 0; "O/P MOVER   ESPACIO DISPARA"
    print at 19, 11; ink 6; bright 0; "MAXIMO "; hiscore; "0"
    print at 21, 9; ink 7; bright 1; flash 1; "PULSA ESPACIO"
    initStars()
    lastf = peek(23672)
    pressed = 1
    do
        syncFrame()
        fc = fc + 1
        moveStars()
        n = (fc >> 3) bAND 1
        drawObj(OBJENEMY, 56, 80, SPR_COLDEYE + n, 16, 69)
        drawObj(OBJENEMY + 1, 120, 80, SPR_SUPERFLY + n, 16, 68)
        drawObj(OBJENEMY + 2, 184, 80, SPR_ATOMIC + n, 16, 67)
        seed = seed + 1
        if (in(32766) bAND 1) = 0 then
            if pressed = 0 then exit do
        else
            pressed = 0
        end if
    loop
    if seed = 0 then seed = 1
end sub

' ---------------------------------------------------------------- main

dim f as ubyte
for f = 0 to NSPR - 1
    poke uinteger FADDR + (cast(uinteger, f) << 1), @sprData(0) + cast(uinteger, f) * 384
next f
orbXBase = @orbX(0)
orbYBase = @orbY(0)
swayXBase = @swayX(0)
swayYBase = @swayY(0)
hiscore = 0
do
    titleScreen()
    playGame()
loop
