from copy import deepcopy
from LSP.plugin.core.protocol import CompletionItem
from LSP.plugin.core.protocol import CompletionItemLabelDetails
from LSP.plugin.core.protocol import CompletionItemTag
from LSP.plugin.core.protocol import InsertTextFormat
from LSP.plugin.core.typing import Any, Generator, List, Dict, Callable, Optional
from LSP.plugin.core.views import format_completion
from setup import TextDocumentTestCase
import sublime


additional_edits = {
    'label': 'asdf',
    'additionalTextEdits': [
        {
            'range': {
                'start': {
                    'line': 0,
                    'character': 0
                },
                'end': {
                    'line': 0,
                    'character': 0
                }
            },
            'newText': 'import asdf;\n'
        }
    ]
}


class CompletionsTestsBase(TextDocumentTestCase):
    @classmethod
    def init_view_settings(cls) -> None:
        super().init_view_settings()
        assert cls.view
        cls.view.settings().set("auto_complete_selector", "text.plain")

    def type(self, text: str) -> None:
        self.view.run_command('append', {'characters': text})
        self.view.run_command('move_to', {'to': 'eol'})

    def move_cursor(self, row: int, col: int) -> None:
        point = self.view.text_point(row, col)
        # move cursor to point
        s = self.view.sel()
        s.clear()
        s.add(point)

    def create_commit_completion_closure(self) -> Callable[[], bool]:
        committed = False
        current_change_count = self.view.change_count()

        def commit_completion() -> bool:
            if not self.view.is_auto_complete_visible():
                return False
            nonlocal committed
            nonlocal current_change_count
            if not committed:
                self.view.run_command("commit_completion")
                committed = True
            return self.view.change_count() > current_change_count

        return commit_completion

    def select_completion(self) -> 'Generator':
        self.view.run_command('auto_complete')
        yield self.create_commit_completion_closure()

    def read_file(self) -> str:
        return self.view.substr(sublime.Region(0, self.view.size()))

    def verify(self, *, completion_items: List[Dict[str, Any]], insert_text: str, expected_text: str) -> Generator:
        if insert_text:
            self.type(insert_text)
        self.set_response("textDocument/completion", completion_items)
        yield from self.select_completion()
        yield from self.await_message("textDocument/completion")
        yield from self.await_message("textDocument/didChange")
        self.assertEqual(self.read_file(), expected_text)


class QueryCompletionsTests(CompletionsTestsBase):
    def test_none(self) -> 'Generator':
        self.set_response("textDocument/completion", None)
        self.view.run_command('auto_complete')
        yield lambda: self.view.is_auto_complete_visible() is False

    def test_simple_label(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{'label': 'asdf'}, {'label': 'efcgh'}],
            insert_text='',
            expected_text='asdf')

    def test_prefer_insert_text_over_label(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{"label": "Label text", "insertText": "Insert text"}],
            insert_text='',
            expected_text='Insert text')

    def test_prefer_text_edit_over_insert_text(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{
                "label": "Label text",
                "insertText": "Insert text",
                "textEdit": {
                    "newText": "Text edit",
                    "range": {
                        "end": {
                            "character": 5,
                            "line": 0
                        },
                        "start": {
                            "character": 0,
                            "line": 0
                        }
                    }
                }
            }],
            insert_text='',
            expected_text='Text edit')

    def test_simple_insert_text(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{'label': 'asdf', 'insertText': 'asdf()'}],
            insert_text="a",
            expected_text='asdf()')

    def test_var_prefix_using_label(self) -> 'Generator':
        yield from self.verify(completion_items=[{'label': '$what'}], insert_text="$", expected_text="$what")

    def test_var_prefix_added_in_insertText(self) -> 'Generator':
        """
        https://github.com/sublimelsp/LSP/issues/294

        User types '$env:U', server replaces '$env:U' with '$env:USERPROFILE'
        """
        yield from self.verify(
            completion_items=[{
                'filterText': '$env:USERPROFILE',
                'insertText': '$env:USERPROFILE',
                'sortText': '0006USERPROFILE',
                'label': 'USERPROFILE',
                'additionalTextEdits': None,
                'data': None,
                'kind': 6,
                'command': None,
                'textEdit': {
                    'newText': '$env:USERPROFILE',
                    'range': {
                        'end': {'line': 0, 'character': 6},
                        'start': {'line': 0, 'character': 0}
                    }
                },
                'commitCharacters': None,
                'range': None,
                'documentation': None
            }],
            insert_text="$env:U",
            expected_text="$env:USERPROFILE")

    def test_pure_insertion_text_edit(self) -> 'Generator':
        """
        https://github.com/sublimelsp/LSP/issues/368

        User types '$so', server returns pure insertion completion 'meParam', completing it to '$someParam'.

        THIS TEST FAILS
        """
        yield from self.verify(
            completion_items=[{
                'textEdit': {
                    'newText': 'meParam',
                    'range': {
                        'end': {'character': 4, 'line': 0},
                        'start': {'character': 4, 'line': 0}  # pure insertion!
                    }
                },
                'label': '$someParam',
                'data': None,
                'command': None,
                'detail': 'null',
                'insertText': None,
                'additionalTextEdits': None,
                'sortText': None,
                'documentation': None,
                'kind': 6
            }],
            insert_text="$so",
            expected_text="$someParam")

    def test_space_added_in_label(self) -> 'Generator':
        """
        Clangd: label=" const", insertText="const" (https://github.com/sublimelsp/LSP/issues/368)
        """
        yield from self.verify(
            completion_items=[{
                "label": " const",
                "sortText": "3f400000const",
                "kind": 14,
                "textEdit": {
                    "newText": "const",
                    "range": {
                        "end": {
                            "character": 1,
                            "line": 0
                        },
                        "start": {
                            "character": 3,
                            "line": 0
                        }
                    }
                },
                "insertTextFormat": InsertTextFormat.Snippet,
                "insertText": "const",
                "filterText": "const",
                "score": 6
            }],
            insert_text=' co',
            expected_text=" const")  # NOT 'const'

    def test_dash_missing_from_label(self) -> 'Generator':
        """
        Powershell: label="UniqueId", trigger="-UniqueIdd, text to be inserted = "-UniqueId"

        (https://github.com/sublimelsp/LSP/issues/572)
        """
        yield from self.verify(
            completion_items=[{
                "filterText": "-UniqueId",
                "documentation": None,
                "textEdit": {
                    "range": {
                        "start": {"character": 0, "line": 0},
                        "end": {"character": 1, "line": 0}
                    },
                    "newText": "-UniqueId"
                },
                "commitCharacters": None,
                "command": None,
                "label": "UniqueId",
                "insertText": "-UniqueId",
                "additionalTextEdits": None,
                "data": None,
                "range": None,
                "insertTextFormat": InsertTextFormat.PlainText,
                "sortText": "0001UniqueId",
                "kind": 6,
                "detail": "[string[]]"
            }],
            insert_text="u",
            expected_text="-UniqueId")

    def test_edit_before_cursor(self) -> 'Generator':
        """
        https://github.com/sublimelsp/LSP/issues/536
        """
        yield from self.verify(
            completion_items=[{
                'insertTextFormat': 2,
                'data': {
                    'symbol': 'example/Foo#myFunction().',
                    'target': 'file:/home/ayoub/workspace/testproject/?id=root'
                },
                'detail': 'override def myFunction(): Unit',
                'sortText': '00000',
                'filterText': 'override def myFunction',  # the filterText is tricky here
                'preselect': True,
                'label': 'override def myFunction(): Unit',
                'kind': 2,
                'additionalTextEdits': [],
                'textEdit': {
                    'newText': 'override def myFunction(): Unit = ${0:???}',
                    'range': {
                        'start': {
                            'line': 0,
                            'character': 0
                        },
                        'end': {
                            'line': 0,
                            'character': 7
                        }
                    }
                }
            }],
            insert_text='def myF',
            expected_text='override def myFunction(): Unit = ???')

    def test_edit_after_nonword(self) -> 'Generator':
        """
        https://github.com/sublimelsp/LSP/issues/645
        """
        yield from self.verify(
            completion_items=[{
                "textEdit": {
                    "newText": "apply($0)",
                    "range": {
                        "end": {
                            "line": 0,
                            "character": 5
                        },
                        "start": {
                            "line": 0,
                            "character": 5
                        }
                    }
                },
                "label": "apply[A](xs: A*): List[A]",
                "sortText": "00000",
                "preselect": True,
                "insertTextFormat": InsertTextFormat.Snippet,
                "filterText": "apply",
                "data": {
                    "symbol": "scala/collection/immutable/List.apply().",
                    "target": "file:/home/user/workspace/testproject/?id=root"
                },
                "kind": 2
            }],
            insert_text="List.",
            expected_text='List.apply()')

    def test_filter_text_is_not_a_prefix_of_label(self) -> 'Generator':
        """
        Metals: "Implement all members"

        The filterText is 'e', so when the user types 'e', one of the completion items should be
        "Implement all members".

        VSCode doesn't show the filterText in this case; it'll only show "Implement all members".
        c.f. https://github.com/microsoft/language-server-protocol/issues/898#issuecomment-593968008

        In SublimeText, we always show the filterText (a.k.a. trigger).

        This is one of the more confusing and contentious completion items.

        https://github.com/sublimelsp/LSP/issues/771
        """
        yield from self.verify(
            completion_items=[{
                "label": "Implement all members",
                "kind": 12,
                "sortText": "00002",
                "filterText": "e",
                "insertTextFormat": InsertTextFormat.Snippet,
                "textEdit": {
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 0, "character": 1}
                    },
                    "newText": "def foo: Int \u003d ${0:???}\n   def boo: Int \u003d ${0:???}"
                },
                "data": {
                    "target": "file:/Users/ckipp/Documents/scala-workspace/test-project/?id\u003droot",
                    "symbol": "local6"
                }
            }],
            insert_text='e',
            expected_text='def foo: Int \u003d ???\n   def boo: Int \u003d ???')

    def test_additional_edits_if_session_has_the_resolve_capability(self) -> 'Generator':
        completion_item = {
            'label': 'asdf'
        }
        self.set_response("completionItem/resolve", {
            'label': 'asdf',
            'additionalTextEdits': [
                {
                    'range': {
                        'start': {
                            'line': 0,
                            'character': 0
                        },
                        'end': {
                            'line': 0,
                            'character': 0
                        }
                    },
                    'newText': 'import asdf;\n'
                }
            ]
        })
        yield from self.verify(
            completion_items=[completion_item],
            insert_text='',
            expected_text='import asdf;\nasdf')

    def test_prefix_should_include_the_dollar_sign(self) -> 'Generator':
        self.set_response(
            'textDocument/completion',
            {
                "items":
                [
                    {
                        "label": "$hello",
                        "textEdit":
                        {
                            "newText": "$hello",
                            "range": {"end": {"line": 2, "character": 3}, "start": {"line": 2, "character": 0}}
                        },
                        "data": 2369386987913238,
                        "detail": "int",
                        "kind": 6,
                        "sortText": "$hello"
                    }
                ],
                "isIncomplete": False
            })

        self.type('<?php\n$hello = "world";\n$he\n?>\n')
        # move cursor after `$he|`
        self.move_cursor(2, 3)
        yield from self.select_completion()
        yield from self.await_message('textDocument/completion')

        self.assertEquals(self.read_file(), '<?php\n$hello = "world";\n$hello\n?>\n')

    def test_fuzzy_match_plaintext_insert_text(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{
                'insertTextFormat': 1,
                'label': 'aaba',
                'insertText': 'aaca'
            }],
            insert_text='aa',
            expected_text='aaca')

    def test_fuzzy_match_plaintext_text_edit(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{
                'insertTextFormat': 1,
                'label': 'aaba',
                'textEdit': {
                    'newText': 'aaca',
                    'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 3}}}
            }],
            insert_text='aab',
            expected_text='aaca')

    def test_fuzzy_match_snippet_insert_text(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{
                'insertTextFormat': 2,
                'label': 'aaba',
                'insertText': 'aaca'
            }],
            insert_text='aab',
            expected_text='aaca')

    def test_fuzzy_match_snippet_text_edit(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{
                'insertTextFormat': 2,
                'label': 'aaba',
                'textEdit': {
                    'newText': 'aaca',
                    'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 3}}}
            }],
            insert_text='aab',
            expected_text='aaca')

    def verify_multi_cursor(self, completion: Dict[str, Any]) -> 'Generator':
        """
        This checks whether `fd` gets replaced by `fmod` when the cursor is at `fd|`.
        Turning the `d` into an `m` is an important part of the test.
        """
        self.type('fd\nfd\nfd')
        selection = self.view.sel()
        selection.clear()
        selection.add(sublime.Region(2, 2))
        selection.add(sublime.Region(5, 5))
        selection.add(sublime.Region(8, 8))
        self.assertEqual(len(selection), 3)
        for region in selection:
            self.assertEqual(self.view.substr(self.view.line(region)), "fd")
        self.set_response("textDocument/completion", [completion])
        yield from self.select_completion()
        yield from self.await_message("textDocument/completion")
        self.assertEqual(self.read_file(), 'fmod()\nfmod()\nfmod()')

    def test_multi_cursor_plaintext_insert_text(self) -> 'Generator':
        yield from self.verify_multi_cursor({
            'insertTextFormat': 1,
            'label': 'fmod(a, b)',
            'insertText': 'fmod()'
        })

    def test_multi_cursor_plaintext_text_edit(self) -> 'Generator':
        yield from self.verify_multi_cursor({
            'insertTextFormat': 1,
            'label': 'fmod(a, b)',
            'textEdit': {
                'newText': 'fmod()',
                'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 2}}
            }
        })

    def test_multi_cursor_snippet_insert_text(self) -> 'Generator':
        yield from self.verify_multi_cursor({
            'insertTextFormat': 2,
            'label': 'fmod(a, b)',
            'insertText': 'fmod($0)'
        })

    def test_multi_cursor_snippet_text_edit(self) -> 'Generator':
        yield from self.verify_multi_cursor({
            'insertTextFormat': 2,
            'label': 'fmod(a, b)',
            'textEdit': {
                'newText': 'fmod($0)',
                'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 2}}
            }
        })

    def test_nontrivial_text_edit_removal(self) -> 'Generator':
        self.type('#include <u>')
        self.move_cursor(0, 11)  # Put the cursor inbetween 'u' and '>'
        self.set_response("textDocument/completion", [{
            'filterText': 'uchar.h>',
            'label': ' uchar.h>',
            'textEdit': {
                # This range should remove "u>" and then insert "uchar.h>"
                'range': {'start': {'line': 0, 'character': 10}, 'end': {'line': 0, 'character': 12}},
                'newText': 'uchar.h>'
            },
            'insertText': 'uchar.h>',
            'kind': 17,
            'insertTextFormat': 2
        }])
        yield from self.select_completion()
        yield from self.await_message("textDocument/completion")
        self.assertEqual(self.read_file(), '#include <uchar.h>')

    def test_nontrivial_text_edit_removal_with_buffer_modifications_clangd(self) -> 'Generator':
        self.type('#include <u>')
        self.move_cursor(0, 11)  # Put the cursor inbetween 'u' and '>'
        self.set_response("textDocument/completion", [{
            'filterText': 'uchar.h>',
            'label': ' uchar.h>',
            'textEdit': {
                # This range should remove "u>" and then insert "uchar.h>"
                'range': {'start': {'line': 0, 'character': 10}, 'end': {'line': 0, 'character': 12}},
                'newText': 'uchar.h>'
            },
            'insertText': 'uchar.h>',
            'kind': 17,
            'insertTextFormat': 2
        }])
        self.view.run_command('auto_complete')  # show the AC widget
        yield from self.await_message("textDocument/completion")
        yield 100
        self.view.run_command('insert', {'characters': 'c'})  # type characters
        yield 100
        self.view.run_command('insert', {'characters': 'h'})  # while the AC widget
        yield 100
        self.view.run_command('insert', {'characters': 'a'})  # is visible
        yield 100
        # Commit the completion. The buffer has been modified in the meantime, so the old text edit that says to
        # remove "u>" is invalid. The code in completion.py must be able to handle this.
        yield self.create_commit_completion_closure()
        self.assertEqual(self.read_file(), '#include <uchar.h>')

    def test_nontrivial_text_edit_removal_with_buffer_modifications_json(self) -> 'Generator':
        self.type('{"k"}')
        self.move_cursor(0, 3)  # Put the cursor inbetween 'k' and '"'
        self.set_response("textDocument/completion", [{
            'kind': 10,
            'documentation': 'Array of single or multiple keys',
            'insertTextFormat': 2,
            'label': 'keys',
            'textEdit': {
                # This range should remove '"k"' and then insert '"keys": []'
                'range': {'start': {'line': 0, 'character': 1}, 'end': {'line': 0, 'character': 4}},
                'newText': '"keys": [$1]'
            },
            "filterText": '"keys"',
            "insertText": 'keys": [$1]'
        }])
        self.view.run_command('auto_complete')  # show the AC widget
        yield from self.await_message("textDocument/completion")
        yield 100
        self.view.run_command('insert', {'characters': 'e'})  # type characters
        yield 100
        self.view.run_command('insert', {'characters': 'y'})  # while the AC widget is open
        yield 100
        # Commit the completion. The buffer has been modified in the meantime, so the old text edit that says to
        # remove '"k"' is invalid. The code in completion.py must be able to handle this.
        yield self.create_commit_completion_closure()
        self.assertEqual(self.read_file(), '{"keys": []}')

    def test_text_edit_plaintext_with_multiple_lines_indented(self) -> Generator[None, None, None]:
        self.type("\t\n\t")
        self.move_cursor(1, 2)
        self.set_response("textDocument/completion", [{
            'label': 'a',
            'textEdit': {
                'range': {'start': {'line': 1, 'character': 4}, 'end': {'line': 1, 'character': 4}},
                'newText': 'a\n\tb'
            },
            'insertTextFormat': InsertTextFormat.PlainText
        }])
        yield from self.select_completion()
        yield from self.await_message("textDocument/completion")
        # the "b" should be intended one level deeper
        self.assertEqual(self.read_file(), '\t\n\ta\n\t\tb')

    def test_show_deprecated_flag(self) -> None:
        item_with_deprecated_flag = {
            "label": 'hello',
            "kind": 2,  # Method
            "deprecated": True
        }  # type: CompletionItem
        formatted_completion_item = format_completion(item_with_deprecated_flag, 0, False, "")
        self.assertIn("DEPRECATED", formatted_completion_item.annotation)

    def test_show_deprecated_tag(self) -> None:
        item_with_deprecated_tags = {
            "label": 'hello',
            "kind": 2,  # Method
            "tags": [CompletionItemTag.Deprecated]
        }  # type: CompletionItem
        formatted_completion_item = format_completion(item_with_deprecated_tags, 0, False, "")
        self.assertIn("DEPRECATED", formatted_completion_item.annotation)

    def test_strips_carriage_return_in_insert_text(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{
                'label': 'greeting',
                'insertText': 'hello\r\nworld'
            }],
            insert_text='',
            expected_text='hello\nworld')

    def test_strips_carriage_return_in_text_edit(self) -> 'Generator':
        yield from self.verify(
            completion_items=[{
                'label': 'greeting',
                'textEdit': {
                    'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 0}},
                    'newText': 'hello\r\nworld'
                }
            }],
            insert_text='',
            expected_text='hello\nworld')

    def test_label_details_with_filter_text(self) -> None:

        def check(
            resolve_support: bool,
            expected_regex: str,
            label: str,
            label_details: Optional[CompletionItemLabelDetails]
        ) -> None:
            lsp = {"label": label, "filterText": "force_label_to_go_into_st_detail_field"}  # type: CompletionItem
            if label_details is not None:
                lsp["labelDetails"] = label_details
            native = format_completion(lsp, 0, resolve_support, "")
            self.assertRegex(native.details, expected_regex)

        check(
            resolve_support=False,
            expected_regex=r"^f$",
            label="f",
            label_details=None
        )
        check(
            resolve_support=False,
            expected_regex=r"^f\(X&amp; x\)$",
            label="f",
            label_details={"detail": "(X& x)"}
        )
        check(
            resolve_support=False,
            expected_regex=r"^f\(X&amp; x\) \| does things$",
            label="f",
            label_details={"detail": "(X& x)", "description": "does things"}
        )
        check(
            resolve_support=True,
            expected_regex=r"^<a href='subl:lsp_resolve_docs {\S+}'>More</a> \| f$",
            label="f",
            label_details=None
        )
        check(
            resolve_support=True,
            expected_regex=r"^<a href='subl:lsp_resolve_docs {\S+}'>More</a> \| f\(X&amp; x\)$",
            label="f",
            label_details={"detail": "(X& x)"}
        )
        check(
            resolve_support=True,
            expected_regex=r"^<a href='subl:lsp_resolve_docs {\S+}'>More</a> \| f\(X&amp; x\) \| does things$",  # noqa: E501
            label="f",
            label_details={"detail": "(X& x)", "description": "does things"}
        )

    def test_label_details_without_filter_text(self) -> None:

        def check(
            resolve_support: bool,
            expected_regex: str,
            label: str,
            label_details: Optional[CompletionItemLabelDetails]
        ) -> None:
            lsp = {"label": label}  # type: CompletionItem
            if label_details is not None:
                lsp["labelDetails"] = label_details
            native = format_completion(lsp, 0, resolve_support, "")
            self.assertRegex(native.trigger, expected_regex)

        check(
            resolve_support=False,
            expected_regex=r"^f$",
            label="f",
            label_details=None
        )
        check(
            resolve_support=False,
            expected_regex=r"^f\(X& x\)$",
            label="f",
            label_details={"detail": "(X& x)"}
        )
        check(
            resolve_support=False,
            expected_regex=r"^f\(X& x\)$",
            label="f",
            label_details={"detail": "(X& x)", "description": "does things"}
        )


class QueryCompletionsNoResolverTests(CompletionsTestsBase):
    '''
    The difference between QueryCompletionsTests and QueryCompletionsNoResolverTests
    is that QueryCompletionsTests has the completion item resolve capability enabled
    and the QueryCompletionsNoResolverTests has the resolve capability disabled
    '''
    @classmethod
    def get_test_server_capabilities(cls) -> dict:
        capabilities = deepcopy(super().get_test_server_capabilities())
        capabilities['capabilities']['completionProvider']['resolveProvider'] = False
        return capabilities

    def test_additional_edits_if_session_does_not_have_the_resolve_capability(self) -> 'Generator':
        completion_item = {
            'label': 'ghjk',
            'additionalTextEdits': [
                {
                    'range': {
                        'start': {
                            'line': 0,
                            'character': 0
                        },
                        'end': {
                            'line': 0,
                            'character': 0
                        }
                    },
                    'newText': 'import ghjk;\n'
                }
            ]
        }
        yield from self.verify(
            completion_items=[completion_item],
            insert_text='',
            expected_text='import ghjk;\nghjk')
