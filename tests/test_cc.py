from territory.c import collect_details, read_compile_commands, remove_arg, parse_vee
from territory_testlib import init_repo


def test_collect_details(tmp_path):
    init_repo(tmp_path / 'repo')
    cc_data = read_compile_commands(tmp_path / 'repo/compile_commands.json')
    td = tmp_path / 't'
    td.mkdir()
    paths = collect_details(td, tmp_path / 'repo', cc_data)
    assert '-target' in cc_data[0]['arguments']
    assert '-target' in cc_data[1]['arguments']
    assert tmp_path / 'repo/mod1.c' in paths
    assert tmp_path / 'repo/shared.h' in paths
    assert tmp_path / 'repo/dir/mod2.c' in paths


def test_collect_details_cc_error(tmp_path):
    init_repo(tmp_path / 'repo')
    (tmp_path / 'repo/mod1.c').write_text('BAD SYNTAX')
    (tmp_path / 'repo/dir/mod2.c').write_text('BAD SYNTAX')

    cc_data = read_compile_commands(tmp_path / 'repo/compile_commands.json')
    td = tmp_path / 't'
    td.mkdir()
    paths = collect_details(td, tmp_path / 'repo', cc_data)
    assert '-target' in cc_data[0]['arguments']
    assert '-target' in cc_data[1]['arguments']
    assert tmp_path / 'repo/mod1.c' in paths
    assert tmp_path / 'repo/dir/mod2.c' in paths
    assert tmp_path / 'repo/shared.h' not in paths


def test_remove_arg():
    assert remove_arg(['cc', '-c', '-o', '/foo', 'bar'], '-o', 2, prefix=True) == ['cc', '-c', 'bar']
    assert remove_arg(['cc', '-c', '-o/foo', 'bar'], '-o', 2, prefix=True) == ['cc', '-c', 'bar']
    assert remove_arg(['cc', '-c', '-o', '/foo', 'bar'], '-o', 2) == ['cc', '-c', 'bar']
    assert remove_arg(['cc', '-c', '-o/foo', 'bar'], '-o', 2) == ['cc', '-c', '-o/foo', 'bar']
    assert remove_arg(['cc', '-c', '-o', '/foo', 'bar'], '-c', 1) == ['cc', '-o', '/foo', 'bar']
    assert remove_arg(['cc', '-Ifoo', '-Ibar', '-Ibaz', '-iLocal', 'f.cc'], '-I', 2, prefix=True) == ['cc', '-iLocal', 'f.cc']


def test_read_vee():
    cc_output = '''Apple clang version 15.0.0 (clang-1500.3.9.4)
Target: arm64-apple-darwin23.6.0
Thread model: posix
InstalledDir: /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin
 "/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang" -cc1 -triple arm64-apple-macosx14.0.0 -Wundef-prefix=TARGET_OS_ -Wdeprecated-objc-isa-usage -Werror=deprecated-objc-isa-usage -Werror=implicit-function-declaration -emit-obj -mrelax-all --mrelax-relocations -disable-free -clear-ast-before-backend -disable-llvm-verifier -discard-value-names -main-file-name test.c -mrelocation-model pic -pic-level 2 -mframe-pointer=non-leaf -fno-strict-return -ffp-contract=on -fno-rounding-math -funwind-tables=1 -fobjc-msgsend-selector-stubs -target-sdk-version=14.5 -fvisibility-inlines-hidden-static-local-var -target-cpu apple-m1 -target-feature +v8.5a -target-feature +crc -target-feature +lse -target-feature +rdm -target-feature +crypto -target-feature +dotprod -target-feature +fp-armv8 -target-feature +neon -target-feature +fp16fml -target-feature +ras -target-feature +rcpc -target-feature +zcm -target-feature +zcz -target-feature +fullfp16 -target-feature +sm4 -target-feature +sha3 -target-feature +sha2 -target-feature +aes -target-abi darwinpcs -debugger-tuning=lldb -target-linker-version 1053.12 -v -fcoverage-compilation-dir=/Users/pawel/territory -resource-dir /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/clang/15.0.0 -isysroot /Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk -I/usr/local/include -internal-isystem /Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/usr/local/include -internal-isystem /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/clang/15.0.0/include -internal-externc-isystem /Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/usr/include -internal-externc-isystem /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/include -Wno-reorder-init-list -Wno-implicit-int-float-conversion -Wno-c99-designator -Wno-final-dtor-non-final-class -Wno-extra-semi-stmt -Wno-misleading-indentation -Wno-quoted-include-in-framework-header -Wno-implicit-fallthrough -Wno-enum-enum-conversion -Wno-enum-float-conversion -Wno-elaborated-enum-base -Wno-reserved-identifier -Wno-gnu-folding-constant -fdebug-compilation-dir=/Users/pawel/territory -ferror-limit 19 -stack-protector 1 -fstack-check -mdarwin-stkchk-strong-link -fblocks -fencode-extended-block-signature -fregister-global-dtors-with-atexit -fgnuc-version=4.2.1 -fmax-type-align=16 -fcommon -fcolor-diagnostics -clang-vendor-feature=+disableNonDependentMemberExprInCurrentInstantiation -fno-odr-hash-protocols -clang-vendor-feature=+enableAggressiveVLAFolding -clang-vendor-feature=+revert09abecef7bbf -clang-vendor-feature=+thisNoAlignAttr -clang-vendor-feature=+thisNoNullAttr -mllvm -disable-aligned-alloc-awareness=1 -D__GCC_HAVE_DWARF2_CFI_ASM=1 -o /tmp/test.o -x c /tmp/test.c
clang -cc1 version 15.0.0 (clang-1500.3.9.4) default target arm64-apple-darwin23.6.0
ignoring nonexistent directory "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/usr/local/include"
ignoring nonexistent directory "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/Library/Frameworks"
#include "..." search starts here:
#include <...> search starts here:
 /tmp/dir with space
 /usr/local/include
 /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/clang/15.0.0/include
 /Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/usr/include
 /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/include
 /Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/System/Library/Frameworks (framework directory)
End of search list.
'''
    vee = parse_vee(cc_output)
    assert vee.target == 'arm64-apple-darwin23.6.0'
    assert vee.angle_bracket_include_paths == [
        '/tmp/dir with space',
        '/usr/local/include',
        '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/lib/clang/15.0.0/include',
        '/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/usr/include',
        '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/include',
        '/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/System/Library/Frameworks',
    ]
