from __future__ import annotations

import io
import sys
from contextlib import contextmanager
from types import MappingProxyType
from typing import Any, Iterator

import pytest

from term_image.geometry import Size
from term_image.padding import AlignedPadding, ExactPadding, HAlign, VAlign
from term_image.render import RenderIterator
from term_image.renderable import (
    Frame,
    FrameCount,
    FrameDuration,
    IndefiniteSeekError,
    Renderable,
    RenderableError,
    RenderArgs,
    RenderArgsError,
    RenderData,
    RenderSizeOutofRangeError,
)

from .. import get_terminal_size

stdout = io.StringIO()
columns, lines = get_terminal_size()

# ========================== Render classes ==========================


class Space(Renderable):
    size = Size(1, 1)

    def _get_render_size_(self):
        return self.size

    def _render_(self, render_data, render_args):
        data = render_data[Renderable]
        width, height = data.size
        return Frame(
            data.frame, data.duration, data.size, "\n".join((" " * width,) * height)
        )


class IndefiniteSpace(Space):
    def __init__(self, frame_count):
        super().__init__(FrameCount.INDEFINITE, 1)
        self.__frame_count = frame_count

    def _render_(self, render_data, render_args):
        if render_data[Renderable].iteration:
            next(render_data[__class__].frames)
        return super()._render_(render_data, render_args)

    def _get_render_data_(self, *, iteration):
        render_data = super()._get_render_data_(iteration=iteration)
        render_data[__class__].frames = (
            iter(range(self.__frame_count)) if iteration else None
        )
        return render_data

    class _Data_(RenderData.Namespace):
        frames: Iterator[int] | None


class Char(Renderable):
    size = Size(1, 1)

    def _get_render_size_(self):
        return self.size

    def _render_(self, render_data, render_args):
        data = render_data[Renderable]
        width, height = data.size
        return Frame(
            data.frame,
            data.duration,
            data.size,
            "\n".join((render_args[Char].char * width,) * height),
        )

    class Args(RenderArgs.Namespace):
        char: str = " "


# ========================== Utils ==========================


@contextmanager
def capture_stdout():
    stdout.seek(0)
    stdout.truncate()
    sys.stdout = stdout
    try:
        yield
    finally:
        stdout.seek(0)
        stdout.truncate()


def draw_n_eol(height, frame_count, loops):
    return (height - 1) * frame_count * loops + 1


# ========================== Tests ==========================


class TestMeta:
    def test_not_a_subclass(self):
        with pytest.raises(RenderableError, match="'Foo' is not a subclass"):

            class Foo(metaclass=type(Renderable)):
                pass

    class TestRenderArgs:
        def test_base(self):
            assert "_ALL_DEFAULT_ARGS" in Renderable.__dict__
            assert isinstance(Renderable._ALL_DEFAULT_ARGS, MappingProxyType)
            assert Renderable._ALL_DEFAULT_ARGS == {}

        def test_invalid_type(self):
            with pytest.raises(TypeError, match="'Foo.Args'"):

                class Foo(Renderable):
                    Args = Ellipsis

        def test_not_a_subclass(self):
            with pytest.raises(
                RenderableError,
                match="'Foo.Args' .* subclass of 'RenderArgs.Namespace'",
            ):

                class Foo(Renderable):
                    class Args:
                        pass

        def test_already_associated(self):
            class Foo(Renderable):
                class Args(RenderArgs.Namespace):
                    foo: None = None

            with pytest.raises(
                RenderableError, match="'Bar.Args' .* associated with .* 'Foo'"
            ):

                class Bar(Renderable):
                    class Args(Foo.Args):
                        pass

        def test_no_args(self):
            class Foo(Renderable):
                pass

            assert Foo.Args is None
            assert "_ALL_DEFAULT_ARGS" in Foo.__dict__
            assert isinstance(Foo._ALL_DEFAULT_ARGS, MappingProxyType)
            assert Foo._ALL_DEFAULT_ARGS == Renderable._ALL_DEFAULT_ARGS

        def test_args_none(self):
            class Foo(Renderable):
                Args = None

            assert Foo.Args is None
            assert "_ALL_DEFAULT_ARGS" in Foo.__dict__
            assert isinstance(Foo._ALL_DEFAULT_ARGS, MappingProxyType)
            assert Foo._ALL_DEFAULT_ARGS == Renderable._ALL_DEFAULT_ARGS

        def test_has_args(self):
            class Args(RenderArgs.Namespace):
                foo: None = None

            Foo = type(Renderable)("Foo", (Renderable,), {"Args": Args})

            assert Foo.Args is Args
            assert "_ALL_DEFAULT_ARGS" in Foo.__dict__
            assert isinstance(Foo._ALL_DEFAULT_ARGS, MappingProxyType)
            assert Foo._ALL_DEFAULT_ARGS == {
                **Renderable._ALL_DEFAULT_ARGS,
                Foo: Foo.Args(),
            }

        def test_association(self):
            class Args(RenderArgs.Namespace):
                foo: None = None

            assert Args.get_render_cls() is None

            Foo = type(Renderable)("Foo", (Renderable,), {"Args": Args})

            assert Args.get_render_cls() is Foo

        class TestInheritance:
            class A(Renderable):
                class Args(RenderArgs.Namespace):
                    a: None = None

            def test_child_with_no_args(self):
                class B(self.A):
                    pass

                assert B._ALL_DEFAULT_ARGS == {
                    **Renderable._ALL_DEFAULT_ARGS,
                    self.A: self.A.Args(),
                }

            def test_parent_with_no_args(self):
                class B(Renderable):
                    pass

                class C(B):
                    class Args(RenderArgs.Namespace):
                        c: None = None

                assert C._ALL_DEFAULT_ARGS == {
                    **Renderable._ALL_DEFAULT_ARGS,
                    C: C.Args(),
                }

            def test_multi_level(self):
                class B(self.A):
                    class Args(RenderArgs.Namespace):
                        b: None = None

                assert B._ALL_DEFAULT_ARGS == {
                    **Renderable._ALL_DEFAULT_ARGS,
                    self.A: self.A.Args(),
                    B: B.Args(),
                }

                class C(B):
                    class Args(RenderArgs.Namespace):
                        c: None = None

                assert C._ALL_DEFAULT_ARGS == {
                    **Renderable._ALL_DEFAULT_ARGS,
                    self.A: self.A.Args(),
                    B: B.Args(),
                    C: C.Args(),
                }

            def test_multiple(self):
                class B(Renderable):
                    class Args(RenderArgs.Namespace):
                        b: None = None

                class C(self.A, B):
                    class Args(RenderArgs.Namespace):
                        c: None = None

                assert C._ALL_DEFAULT_ARGS == {
                    **Renderable._ALL_DEFAULT_ARGS,
                    self.A: self.A.Args(),
                    B: B.Args(),
                    C: C.Args(),
                }

            def test_complex(self):
                class B(self.A):
                    class Args(RenderArgs.Namespace):
                        b: None = None

                class C(self.A):
                    class Args(RenderArgs.Namespace):
                        c: None = None

                class D(B, C):
                    class Args(RenderArgs.Namespace):
                        d: None = None

                class E(Renderable):
                    class Args(RenderArgs.Namespace):
                        e: None = None

                class F(D, E):
                    class Args(RenderArgs.Namespace):
                        f: None = None

                assert F._ALL_DEFAULT_ARGS == {
                    **Renderable._ALL_DEFAULT_ARGS,
                    self.A: self.A.Args(),
                    B: B.Args(),
                    C: C.Args(),
                    D: D.Args(),
                    E: E.Args(),
                    F: F.Args(),
                }

        def test_optimization_default_namespaces_interned(self):
            class A(Renderable):
                class Args(RenderArgs.Namespace):
                    a: None = None

            class B(A):
                class Args(RenderArgs.Namespace):
                    b: None = None

            class C(B):
                class Args(RenderArgs.Namespace):
                    c: None = None

            assert A._ALL_DEFAULT_ARGS[A] is B._ALL_DEFAULT_ARGS[A]
            assert A._ALL_DEFAULT_ARGS[A] is C._ALL_DEFAULT_ARGS[A]
            assert B._ALL_DEFAULT_ARGS[B] is C._ALL_DEFAULT_ARGS[B]

    class TestRenderData:
        def test_base(self):
            assert "_RENDER_DATA_MRO" in Renderable.__dict__
            assert isinstance(Renderable._RENDER_DATA_MRO, MappingProxyType)
            assert Renderable._RENDER_DATA_MRO == {Renderable: Renderable._Data_}

        def test_invalid_type(self):
            with pytest.raises(TypeError, match="'Foo._Data_'"):

                class Foo(Renderable):
                    _Data_ = Ellipsis

        def test_not_a_subclass(self):
            with pytest.raises(
                RenderableError,
                match="'Foo._Data_' .* subclass of 'RenderData.Namespace'",
            ):

                class Foo(Renderable):
                    class _Data_:
                        pass

        def test_already_associated(self):
            class Foo(Renderable):
                class _Data_(RenderData.Namespace):
                    foo: None = None

            with pytest.raises(
                RenderableError, match="'Bar._Data_' .* associated with .* 'Foo'"
            ):

                class Bar(Renderable):
                    class _Data_(Foo._Data_):
                        pass

        def test_no_data(self):
            class Foo(Renderable):
                pass

            assert Foo._Data_ is None
            assert "_RENDER_DATA_MRO" in Foo.__dict__
            assert isinstance(Foo._RENDER_DATA_MRO, MappingProxyType)
            assert Foo._RENDER_DATA_MRO == Renderable._RENDER_DATA_MRO

        def test_data_none(self):
            class Foo(Renderable):
                _Data_ = None

            assert Foo._Data_ is None
            assert "_RENDER_DATA_MRO" in Foo.__dict__
            assert isinstance(Foo._RENDER_DATA_MRO, MappingProxyType)
            assert Foo._RENDER_DATA_MRO == Renderable._RENDER_DATA_MRO

        def test_has_data(self):
            class _Data_(RenderData.Namespace):
                foo: None = None

            Foo = type(Renderable)("Foo", (Renderable,), {"_Data_": _Data_})

            assert Foo._Data_ is _Data_
            assert "_RENDER_DATA_MRO" in Foo.__dict__
            assert isinstance(Foo._RENDER_DATA_MRO, MappingProxyType)
            assert Foo._RENDER_DATA_MRO == {
                **Renderable._RENDER_DATA_MRO,
                Foo: Foo._Data_,
            }

        def test_association(self):
            class _Data_(RenderData.Namespace):
                foo: None = None

            assert _Data_.get_render_cls() is None

            Foo = type(Renderable)("Foo", (Renderable,), {"_Data_": _Data_})

            assert _Data_.get_render_cls() is Foo

        class TestInheritance:
            class A(Renderable):
                class _Data_(RenderData.Namespace):
                    a: None = None

            def test_child_with_no_data(self):
                class B(self.A):
                    pass

                assert B._RENDER_DATA_MRO == {
                    **Renderable._RENDER_DATA_MRO,
                    self.A: self.A._Data_,
                }

            def test_parent_with_no_data(self):
                class B(Renderable):
                    pass

                class C(B):
                    class _Data_(RenderData.Namespace):
                        c: None = None

                assert C._RENDER_DATA_MRO == {
                    **Renderable._RENDER_DATA_MRO,
                    C: C._Data_,
                }

            def test_multi_level(self):
                class B(self.A):
                    class _Data_(RenderData.Namespace):
                        b: None = None

                assert B._RENDER_DATA_MRO == {
                    **Renderable._RENDER_DATA_MRO,
                    self.A: self.A._Data_,
                    B: B._Data_,
                }

                class C(B):
                    class _Data_(RenderData.Namespace):
                        c: None = None

                assert C._RENDER_DATA_MRO == {
                    **Renderable._RENDER_DATA_MRO,
                    self.A: self.A._Data_,
                    B: B._Data_,
                    C: C._Data_,
                }

            def test_multiple(self):
                class B(Renderable):
                    class _Data_(RenderData.Namespace):
                        b: None = None

                class C(self.A, B):
                    class _Data_(RenderData.Namespace):
                        c: None = None

                assert C._RENDER_DATA_MRO == {
                    **Renderable._RENDER_DATA_MRO,
                    self.A: self.A._Data_,
                    B: B._Data_,
                    C: C._Data_,
                }

            def test_complex(self):
                class B(self.A):
                    class _Data_(RenderData.Namespace):
                        b: None = None

                class C(self.A):
                    class _Data_(RenderData.Namespace):
                        c: None = None

                class D(B, C):
                    class _Data_(RenderData.Namespace):
                        d: None = None

                class E(Renderable):
                    class _Data_(RenderData.Namespace):
                        e: None = None

                class F(D, E):
                    class _Data_(RenderData.Namespace):
                        f: None = None

                assert F._RENDER_DATA_MRO == {
                    **Renderable._RENDER_DATA_MRO,
                    self.A: self.A._Data_,
                    B: B._Data_,
                    C: C._Data_,
                    D: D._Data_,
                    E: E._Data_,
                    F: F._Data_,
                }

    class TestExportedAttrs:
        class A(Renderable):
            _EXPORTED_ATTRS_ = ("a",)
            _EXPORTED_DESCENDANT_ATTRS_ = ("A",)

        def test_base(self):
            assert isinstance(Renderable._ALL_EXPORTED_ATTRS, tuple)
            assert Renderable._ALL_EXPORTED_ATTRS == ()

        def test_cls(self):
            assert isinstance(self.A._ALL_EXPORTED_ATTRS, tuple)
            assert sorted(self.A._ALL_EXPORTED_ATTRS) == sorted(("a", "A"))

        def test_inheritance(self):
            class B(self.A):
                _EXPORTED_ATTRS_ = ("b",)
                _EXPORTED_DESCENDANT_ATTRS_ = ("B",)

            assert sorted(B._ALL_EXPORTED_ATTRS) == sorted(("b", "A", "B"))

            class C(B):
                _EXPORTED_ATTRS_ = ("c",)
                _EXPORTED_DESCENDANT_ATTRS_ = ("C",)

            assert sorted(C._ALL_EXPORTED_ATTRS) == sorted(("c", "A", "B", "C"))

        def test_multiple_inheritance(self):
            class B(Renderable):
                _EXPORTED_ATTRS_ = ("b",)
                _EXPORTED_DESCENDANT_ATTRS_ = ("B",)

            class C(self.A, B):
                _EXPORTED_ATTRS_ = ("c",)
                _EXPORTED_DESCENDANT_ATTRS_ = ("C",)

            assert sorted(C._ALL_EXPORTED_ATTRS) == sorted(("c", "A", "B", "C"))

            class C(B, self.A):
                _EXPORTED_ATTRS_ = ("c",)
                _EXPORTED_DESCENDANT_ATTRS_ = ("C",)

            assert sorted(C._ALL_EXPORTED_ATTRS) == sorted(("c", "A", "B", "C"))

        class TestConflict:
            class A(Renderable):
                _EXPORTED_ATTRS_ = ("a",)
                _EXPORTED_DESCENDANT_ATTRS_ = ("A",)

            def test_cls_vs_base(self):
                class B(self.A):
                    _EXPORTED_ATTRS_ = ("a",)
                    _EXPORTED_DESCENDANT_ATTRS_ = ("A",)

                assert sorted(B._ALL_EXPORTED_ATTRS) == sorted(("a", "A"))

            def test_cls_vs_base_of_base(self):
                class B(self.A):
                    _EXPORTED_ATTRS_ = ("b",)
                    _EXPORTED_DESCENDANT_ATTRS_ = ("B",)

                class C(B):
                    _EXPORTED_ATTRS_ = ("a",)
                    _EXPORTED_DESCENDANT_ATTRS_ = ("A",)

                assert sorted(C._ALL_EXPORTED_ATTRS) == sorted(("a", "A", "B"))

            def test_base_vs_base(self):
                class B(Renderable):
                    _EXPORTED_ATTRS_ = ("a",)
                    _EXPORTED_DESCENDANT_ATTRS_ = ("A",)

                class C(self.A, B):
                    _EXPORTED_ATTRS_ = ("c",)
                    _EXPORTED_DESCENDANT_ATTRS_ = ("C",)

                assert sorted(C._ALL_EXPORTED_ATTRS) == sorted(("c", "A", "C"))

                class C(B, self.A):
                    _EXPORTED_ATTRS_ = ("c",)
                    _EXPORTED_DESCENDANT_ATTRS_ = ("C",)

                assert sorted(C._ALL_EXPORTED_ATTRS) == sorted(("c", "A", "C"))

            def test_specific_vs_descendant(self):
                class B(self.A):
                    _EXPORTED_ATTRS_ = ("A",)

                assert sorted(B._ALL_EXPORTED_ATTRS) == sorted(("A",))


class TestInit:
    def test_args(self):
        with pytest.raises(TypeError, match="'frame_count'"):
            Space(Ellipsis, 1)

        for value in (0, -1, -100):
            with pytest.raises(ValueError, match="'frame_count'"):
                Space(value, 1)

        with pytest.raises(TypeError, match="'frame_duration'"):
            Space(2, Ellipsis)

        for value in (0, -1, -100):
            with pytest.raises(ValueError, match="'frame_duration'"):
                Space(2, value)

    def test_ignore_frame_duration_for_non_animated(self):
        Space(1, Ellipsis)


def test_animated():
    assert not Space(1, 1).animated

    for value in (2, *FrameCount):
        assert Space(value, 1).animated


class TestProperties:
    def test_frame_count(self):
        class PostponedSpace(Space):
            def __init__(self, frame_count):
                super().__init__(FrameCount.POSTPONED, 1)
                self.__frame_count = frame_count

            def _get_frame_count_(self):
                return self.__frame_count

        for value in (1, 2, FrameCount.INDEFINITE):
            assert Space(value, 1).frame_count == value

        space = Space(FrameCount.POSTPONED, 1)
        with pytest.raises(NotImplementedError):
            space.frame_count

        for value in (2, FrameCount.INDEFINITE):
            assert PostponedSpace(value).frame_count == value

    class TestFrameDuration:
        def test_get(self):
            for value in (1, 2, 100, FrameDuration.DYNAMIC):
                assert Space(1, value).frame_duration is None
                assert Space(2, value).frame_duration == value

        class TestSet:
            def test_non_animated(self):
                space = Space(1, 1)
                space.frame_duration = 100
                assert space.frame_duration is None

            def test_animated(self):
                anim_space = Space(2, 1)

                with pytest.raises(TypeError, match="'frame_duration'"):
                    anim_space.frame_duration = Ellipsis

                for value in (0, -1, -100):
                    with pytest.raises(ValueError, match="'frame_duration'"):
                        anim_space.frame_duration = value

                for value in (1, 2, 100, FrameDuration.DYNAMIC):
                    anim_space.frame_duration = value
                    assert anim_space.frame_duration == value

    def test_render_size(self):
        space = Space(1, 1)
        assert space.render_size == Size(1, 1)

        space.size = Size(100, 100)
        assert space.render_size == Size(100, 100)


def test_iter():
    space = Space(1, 1)
    with pytest.raises(ValueError, match="not animated"):
        iter(space)

    r_iter = iter(Space(2, 1))
    assert isinstance(r_iter, RenderIterator)
    assert r_iter.loop == 1


def test_str():
    assert str(Space(1, 1)) == " "


class TestDraw:
    @capture_stdout()
    def test_args(self):
        for space in (Space(1, 1), Space(2, 1)):
            with pytest.raises(TypeError, match="'render_args'"):
                space.draw(Ellipsis)
            with pytest.raises(RenderArgsError, match="incompatible"):
                space.draw(RenderArgs(Char))

            with pytest.raises(TypeError, match="'padding'"):
                space.draw(padding=Ellipsis)

            with pytest.raises(TypeError, match="'check_size'"):
                space.draw(check_size=Ellipsis)

            with pytest.raises(TypeError, match="'scroll'"):
                space.draw(scroll=Ellipsis)

    class TestNonAnimation:
        space = Space(1, 1)
        anim_space = Space(2, 1)
        char = Char(1, 1)

        @capture_stdout()
        def test_args_ignored(self):
            # ignored for non-animated renderables
            self.space.draw(animate=Ellipsis)
            self.space.draw(loops=Ellipsis)
            self.space.draw(cache=Ellipsis)

        @capture_stdout()
        def test_default(self):
            self.space.draw()
            assert stdout.getvalue().count("\n") == draw_n_eol(lines - 2, 1, 1)
            assert stdout.getvalue().endswith("\n")

        # Just ensures the argument is passed on and used appropriately.
        # The full tests are at `TestInitRender`.
        @capture_stdout()
        def test_render_args(self):
            self.char.draw(+Char.Args("\u2850"))
            assert stdout.getvalue().count("\n") == draw_n_eol(lines - 2, 1, 1)
            assert stdout.getvalue().count("\u2850") == 1
            assert stdout.getvalue().endswith("\n")

        # Just ensures the argument is passed on and used appropriately.
        # The full tests are at `TestInitRender`.
        @capture_stdout()
        def test_padding(self):
            self.space.draw(padding=AlignedPadding(3, 3))
            assert stdout.getvalue().count("\n") == draw_n_eol(3, 1, 1)
            assert stdout.getvalue().endswith("\n")

        def test_animate(self):
            with capture_stdout():
                self.space.draw()
                output = stdout.getvalue()

            with capture_stdout():
                self.space.draw(animate=True)
                assert output == stdout.getvalue()

            with capture_stdout():
                self.space.draw(animate=False)
                assert output == stdout.getvalue()

            with capture_stdout():
                self.anim_space.draw(animate=False)
                assert output == stdout.getvalue()

        # Just ensures the argument is passed on and used appropriately.
        # The full tests are at `TestInitRender`.
        class TestSizeValidation:
            space = Space(1, 1)

            @capture_stdout()
            def test_check_size(self):
                space = Space(1, 1)
                space.size = Size(columns + 1, 1)
                padding = AlignedPadding(columns + 1, 1)

                # Default
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    space.draw()
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.space.draw(padding=padding)

                # True
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    space.draw(check_size=True)
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.space.draw(padding=padding, check_size=True)

                # False
                space.draw(check_size=False)
                self.space.draw(padding=padding, check_size=False)

            @capture_stdout()
            def test_scroll(self):
                space = Space(1, 1)
                space.size = Size(1, lines + 1)
                padding = AlignedPadding(1, lines + 1)

                # Default
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    space.draw()
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.space.draw(padding=padding)

                # False
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    space.draw(scroll=False)
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.space.draw(padding=padding, scroll=False)

                # True
                self.space.draw(scroll=True)
                self.space.draw(padding=padding, scroll=True)

    class TestAnimation:
        anim_space = Space(2, 1)
        anim_char = Char(2, 1)

        @capture_stdout()
        def test_args(self):
            with pytest.raises(TypeError, match="'animate'"):
                self.anim_space.draw(animate=Ellipsis)

            with pytest.raises(TypeError, match="'loops'"):
                self.anim_space.draw(loops=Ellipsis)

            with pytest.raises(TypeError, match="'cache'"):
                self.anim_space.draw(cache=Ellipsis)

        # Just ensures the argument is passed on and used appropriately.
        # The full tests are at `TestInitRender`.
        @capture_stdout()
        def test_render_args(self):
            self.anim_char.draw(+Char.Args("\u2850"), loops=1)
            assert stdout.getvalue().count("\n") == draw_n_eol(lines - 2, 2, 1)
            assert stdout.getvalue().count("\u2850") == 2
            assert stdout.getvalue().endswith("\n")

        # Just ensures the argument is passed on and used appropriately.
        # The full tests are at `TestInitRender`.
        @capture_stdout()
        def test_padding(self):
            self.anim_space.draw(padding=AlignedPadding(3, 3), loops=1)
            assert stdout.getvalue().count("\n") == draw_n_eol(3, 2, 1)
            assert stdout.getvalue().endswith("\n")

        def test_animate(self):
            with capture_stdout():
                self.anim_space.draw(loops=1)
                output = stdout.getvalue()

            with capture_stdout():
                self.anim_space.draw(animate=True, loops=1)
                assert output == stdout.getvalue()

            with capture_stdout():
                self.anim_space.draw(animate=False, loops=1)
                assert output != stdout.getvalue()

        # Just ensures the argument is passed on and used appropriately.
        # The full tests are at `TestInitRender`.
        class TestSizeValidation:
            anim_space = Space(2, 1)

            @capture_stdout()
            def test_check_size(self):
                anim_space = Space(2, 1)
                anim_space.size = Size(columns + 1, 1)
                padding = AlignedPadding(columns + 1, 1)

                # Default
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    anim_space.draw()
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.anim_space.draw(padding=padding)

                # True
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    anim_space.draw(check_size=True)
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.anim_space.draw(padding=padding, check_size=True)

                # False
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    anim_space.draw(check_size=False)
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render width"
                ):
                    self.anim_space.draw(padding=padding, check_size=False)

            @capture_stdout()
            def test_scroll(self):
                anim_space = Space(2, 1)
                anim_space.size = Size(1, lines + 1)
                padding = AlignedPadding(1, lines + 1)

                # Default
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    anim_space.draw()
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.anim_space.draw(padding=padding)

                # False
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    anim_space.draw(scroll=False)
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.anim_space.draw(padding=padding, scroll=False)

                # True
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    anim_space.draw(scroll=True)
                with pytest.raises(
                    RenderSizeOutofRangeError, match="Padded render height"
                ):
                    self.anim_space.draw(padding=padding, scroll=True)

        class TestDefinite:
            # Can't test the default for definite frame count since it loops infinitely

            def test_loops(self):
                anim_space = Space(2, 1)
                for loops in (1, 2, 10):
                    with capture_stdout():
                        anim_space.draw(loops=loops)
                        assert stdout.getvalue().count("\n") == draw_n_eol(
                            lines - 2, 2, loops
                        )
                        assert stdout.getvalue().endswith("\n")

            def test_frame_count(self):
                for count in (2, 3, 10):
                    with capture_stdout():
                        Space(count, 1).draw(loops=1)
                        assert stdout.getvalue().count("\n") == draw_n_eol(
                            lines - 2, count, 1
                        )
                        assert stdout.getvalue().endswith("\n")

        class TestIndefinite:
            @capture_stdout()
            def test_default(self):
                IndefiniteSpace(2).draw()
                assert stdout.getvalue().count("\n") == draw_n_eol(lines - 2, 2, 1)
                assert stdout.getvalue().endswith("\n")

            def test_loops(self):
                for loops in (1, 2, 10, -1):
                    with capture_stdout():
                        IndefiniteSpace(2).draw(loops=loops)
                        assert stdout.getvalue().count("\n") == draw_n_eol(
                            lines - 2, 2, 1
                        )
                        assert stdout.getvalue().endswith("\n")

            def test_frame_count(self):
                for count in (2, 3, 10):
                    with capture_stdout():
                        IndefiniteSpace(count).draw()
                        assert stdout.getvalue().count("\n") == draw_n_eol(
                            lines - 2, count, 1
                        )
                        assert stdout.getvalue().endswith("\n")


class TestRender:
    space = Space(1, 1)

    def test_args(self):
        with pytest.raises(TypeError, match="'render_args'"):
            self.space.render(Ellipsis)
        with pytest.raises(RenderArgsError, match="incompatible"):
            self.space.render(RenderArgs(Char))

        with pytest.raises(TypeError, match="'padding'"):
            self.space.render(padding=Ellipsis)

    def test_default(self):
        render = self.space.render().render
        assert render == " "
        assert render == str(self.space)
        assert render == self.space.render(None).render
        assert render == self.space.render(padding=ExactPadding()).render
        assert render == self.space.render(padding=AlignedPadding(1, 1)).render

    # Just ensures the argument is passed on and used appropriately.
    # The full tests are at `TestInitRender`.
    def test_render_args(self):
        char = Char(1, 1)
        assert char.render(+Char.Args("\u2850")).render == "\u2850"

    # Just ensures the argument is passed on and used appropriately.
    # The full tests are at `TestInitRender`.
    def test_padding(self):
        assert self.space.render(padding=AlignedPadding(3, 3)).render == "   \n   \n   "


class TestSeekTell:
    def test_definite(self):
        space = Space(10, 1)
        assert space.tell() == 0

        with pytest.raises(TypeError, match="'offset'"):
            space.seek(Ellipsis)

        with pytest.raises(ValueError, match="'offset'"):
            space.seek(-1)

        assert space.tell() == 0
        space.seek(1)
        assert space.tell() == 1
        space.seek(9)
        assert space.tell() == 9

        with pytest.raises(ValueError, match="'offset'"):
            space.seek(10)

        assert space.tell() == 9

    def test_indefinite(self):
        space = Space(FrameCount.INDEFINITE, 1)
        assert space.tell() == 0

        for value in (0, 1):
            with pytest.raises(IndefiniteSeekError):
                space.seek(value)

        assert space.tell() == 0


class TestGetRenderData:
    anim_space = Space(10, 1)

    def test_render_data(self):
        render_data = self.anim_space._get_render_data_(iteration=False)
        assert isinstance(render_data, RenderData)
        assert render_data.render_cls is Space

    def test_size(self):
        for value in (2, 10):
            self.anim_space.size = render_size = Size(value, value)
            render_data = self.anim_space._get_render_data_(iteration=False)
            size = render_data[Renderable].size
            assert isinstance(size, Size)
            assert size == render_size

    def test_frame(self):
        for value in (2, 8):
            self.anim_space.seek(value)
            render_data = self.anim_space._get_render_data_(iteration=False)
            frame = render_data[Renderable].frame
            assert isinstance(frame, int)
            assert frame == value

    def test_duration(self):
        for value in (2, 100, FrameDuration.DYNAMIC):
            self.anim_space.frame_duration = value
            render_data = self.anim_space._get_render_data_(iteration=False)
            duration = render_data[Renderable].duration
            assert isinstance(duration, (int, FrameDuration))
            assert duration == value

    def test_iteration(self):
        render_data = self.anim_space._get_render_data_(iteration=False)
        assert render_data[Renderable].iteration is False

        render_data = self.anim_space._get_render_data_(iteration=True)
        assert render_data[Renderable].iteration is True


class TestInitRender:
    space = Space(1, 1)
    anim_space = Space(2, 1)
    char = Char(1, 1)

    class TestReturnValue:
        space = Space(1, 1)

        def test_default(self):
            return_value = self.space._init_render_(lambda *_: None)

            assert isinstance(return_value, tuple)
            assert len(return_value) == 2

            renderer_return, padding = return_value

            assert renderer_return is None
            assert padding is None

        def test_renderer_return(self):
            for value in (None, 2, "", (), []):
                assert self.space._init_render_(lambda *_: value)[0] is value

        # See also: `TestInitRender.TestPadding`
        def test_padding(self):
            assert self.space._init_render_(lambda *_: None)[1] is None
            assert self.space._init_render_(lambda *_: None, padding=None)[1] is None
            assert isinstance(
                self.space._init_render_(lambda *_: None, padding=ExactPadding())[1],
                ExactPadding,
            )

    def test_renderer(self):
        for renderable, render_cls in ((self.space, Space), (self.char, Char)):
            renderer_args = renderable._init_render_(lambda *args: args)[0]

            assert isinstance(renderer_args, tuple)
            assert len(renderer_args) == 2

            render_data, render_args = renderer_args

            assert isinstance(render_data, RenderData)
            assert render_data.render_cls is render_cls

            assert isinstance(render_args, RenderArgs)
            assert render_args.render_cls is render_cls

    # See also: `TestInitRender.test_iteration`
    def test_render_data(self):
        class Foo(Renderable):
            _render_ = None

            def _get_render_size_(self):
                pass

            def __init__(self, value):
                super().__init__(1, 1)
                self.__value = value

            def _get_render_data_(self, *, iteration):
                render_data = super()._get_render_data_(iteration=iteration)
                render_data[__class__].foo = self.__value
                return render_data

            class _Data_(RenderData.Namespace):
                foo: Any

        for value in (None, 1, " ", []):
            render_data = Foo(value)._init_render_(lambda *args: args)[0][0]

            assert isinstance(render_data, RenderData)
            assert render_data.render_cls is Foo
            assert render_data[Foo].foo is value

    class TestRenderArgs:
        char = Char(1, 1)

        def test_default(self):
            render_args = self.char._init_render_(lambda *args: args)[0][1]

            assert isinstance(render_args, RenderArgs)
            assert render_args.render_cls is Char
            assert render_args[Char].char == " "

            assert (
                render_args == self.char._init_render_(lambda *args: args, None)[0][1]
            )

            assert (
                render_args
                == self.char._init_render_(lambda *args: args, RenderArgs(Char))[0][1]
            )

        def test_non_default(self):
            for value in "123abc":
                render_args = self.char._init_render_(
                    lambda *args: args, +Char.Args(value)
                )[0][1]

                assert isinstance(render_args, RenderArgs)
                assert render_args.render_cls is Char
                assert render_args[Char].char == value

        def test_compatible(self):
            assert (
                self.char._init_render_(
                    lambda *args: args, RenderArgs(Renderable)
                )[0][1]
                == RenderArgs(Char)  # fmt: skip
            )

        def test_incompatible(self):
            with pytest.raises(RenderArgsError, match="incompatible"):
                self.char._init_render_(lambda *_: None, RenderArgs(Space))

    class TestPadding:
        space = Space(1, 1)

        def test_default(self):
            assert self.space._init_render_(lambda *_: None)[1] is None
            assert self.space._init_render_(lambda *_: None, padding=None)[1] is None

        def test_exact(self):
            orig_padding = ExactPadding(1, 2, 3, 4)
            padding = self.space._init_render_(lambda *_: None, padding=orig_padding)[1]
            assert padding is orig_padding

        def test_aligned_absolute(self):
            orig_padding = AlignedPadding(2, 3)
            padding = self.space._init_render_(lambda *_: None, padding=orig_padding)[1]
            assert padding is orig_padding

        def test_aligned_relative(self):
            orig_padding = AlignedPadding(0, -1)
            padding = self.space._init_render_(lambda *_: None, padding=orig_padding)[1]
            assert padding == orig_padding.resolve(get_terminal_size())

        @pytest.mark.parametrize(
            "orig_padding",
            [
                AlignedPadding(1, 2, HAlign.LEFT, VAlign.BOTTOM),
                AlignedPadding(0, -1, HAlign.RIGHT, VAlign.TOP),
            ],
        )
        def test_aligned_alignment(self, orig_padding):
            padding = self.space._init_render_(lambda *_: None, padding=orig_padding)[1]
            assert padding.h_align is orig_padding.h_align
            assert padding.v_align is orig_padding.v_align

    def test_iteration(self):
        render_data = self.space._init_render_(lambda *args: args)[0][0]

        assert render_data[Renderable].iteration is False

        for value in (False, True):
            render_data = self.space._init_render_(  # fmt: skip
                lambda *args: args, iteration=value
            )[0][0]

            assert render_data[Renderable].iteration is value

    def test_finalize(self):
        render_data = self.space._init_render_(lambda *args: args)[0][0]

        assert render_data.finalized

        for value in (False, True):
            render_data = self.space._init_render_(  # fmt: skip
                lambda *args: args, finalize=value
            )[0][0]

            assert render_data.finalized is value

    class TestSizeValidation:
        space = Space(1, 1)

        class TestAnimationFalse:
            class TestCheckSize:
                def test_render_width(self):
                    anim_space = Space(2, 1)

                    # in range
                    anim_space.size = Size(columns, 1)
                    anim_space._init_render_(lambda *_: None, check_size=True)

                    # out of range
                    anim_space.size = Size(columns + 1, 1)

                    # # Default
                    anim_space._init_render_(lambda *_: None)

                    # # False
                    anim_space._init_render_(lambda *_: None, check_size=False)

                    # # True
                    with pytest.raises(RenderSizeOutofRangeError, match="Render width"):
                        anim_space._init_render_(lambda *_: None, check_size=True)

                def test_padded_width(self):
                    anim_space = Space(2, 1)

                    # in range
                    anim_space._init_render_(
                        lambda *_: None,
                        padding=AlignedPadding(columns, 1),
                        check_size=True,
                    )

                    # out of range
                    padding = AlignedPadding(columns + 1, 1)

                    # # Default
                    anim_space._init_render_(
                        lambda *_: None,
                        padding=padding,
                    )

                    # # False
                    anim_space._init_render_(
                        lambda *_: None,
                        padding=padding,
                        check_size=False,
                    )

                    # # True
                    with pytest.raises(
                        RenderSizeOutofRangeError, match="Padded render width"
                    ):
                        anim_space._init_render_(
                            lambda *_: None,
                            padding=padding,
                            check_size=True,
                        )

            class TestScroll:
                def test_render_height(self):
                    anim_space = Space(2, 1)

                    # in range
                    anim_space.size = Size(1, lines)
                    anim_space._init_render_(
                        lambda *_: None, check_size=True, scroll=False
                    )

                    # out of range
                    anim_space.size = Size(1, lines + 1)

                    # # Default
                    with pytest.raises(
                        RenderSizeOutofRangeError, match="Render height"
                    ):
                        anim_space._init_render_(lambda *_: None, check_size=True)

                    # # False
                    with pytest.raises(
                        RenderSizeOutofRangeError, match="Render height"
                    ):
                        anim_space._init_render_(
                            lambda *_: None, check_size=True, scroll=False
                        )

                    # # True
                    anim_space._init_render_(
                        lambda *_: None, check_size=True, scroll=True
                    )

                    # # ignored when check_size is False
                    anim_space._init_render_(
                        lambda *_: None, check_size=False, scroll=False
                    )

                def test_padded_height(self):
                    anim_space = Space(2, 1)

                    # in range
                    anim_space._init_render_(
                        lambda *_: None,
                        padding=AlignedPadding(1, lines),
                        check_size=True,
                        scroll=False,
                    )

                    # out of range
                    padding = AlignedPadding(1, lines + 1)

                    # # Default
                    with pytest.raises(
                        RenderSizeOutofRangeError, match="Padded render height"
                    ):
                        anim_space._init_render_(
                            lambda *_: None,
                            padding=padding,
                            check_size=True,
                        )

                    # # False
                    with pytest.raises(
                        RenderSizeOutofRangeError, match="Padded render height"
                    ):
                        anim_space._init_render_(
                            lambda *_: None,
                            padding=padding,
                            check_size=True,
                            scroll=False,
                        )

                    # # True
                    anim_space._init_render_(
                        lambda *_: None,
                        padding=padding,
                        check_size=True,
                        scroll=True,
                    )

                    # # ignored when check_size is False
                    anim_space._init_render_(
                        lambda *_: None,
                        padding=padding,
                        check_size=False,
                        scroll=False,
                    )

        class TestAnimationTrue:
            def test_check_size_is_ignored(self):
                anim_space = Space(2, 1)
                anim_space.size = Size(columns + 1, 1)

                with pytest.raises(RenderSizeOutofRangeError, match="Render width"):
                    anim_space._init_render_(
                        lambda *_: None, animation=True, check_size=False
                    )

            def test_scroll_is_ignored(self):
                anim_space = Space(2, 1)
                anim_space.size = Size(1, lines + 1)

                with pytest.raises(RenderSizeOutofRangeError, match="Render height"):
                    anim_space._init_render_(
                        lambda *_: None, animation=True, check_size=True, scroll=True
                    )
