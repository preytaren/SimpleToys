__author__ = 'preyta'
import re


class CodeBuilder(object):
    INDENT_STEP = 4

    def __init__(self, indent_level=0):
        self.code = []
        self.indent_level = indent_level

    def add_line(self, line):
        self.code.append(' ' * self.indent_level + line + '\n')

    def add_section(self):
        section = CodeBuilder(indent_level=self.indent_level)
        self.code.append(section)
        return section

    def indent(self):
        self.indent_level += self.INDENT_STEP

    def dedent(self):
        self.indent_level -= self.INDENT_STEP

    def get_globals(self):
        assert self.indent_level == 0
        python_source = str(self)
        global_namespace = {}
        exec (python_source, global_namespace)
        return global_namespace

    def __str__(self):
        result = ''.join(str(code) for code in self.code)
        print result
        return result


class Templite(object):
    SPLIT_PATTERN = re.compile(r'(\{\{.*?\}\}|\{\%.*?\%\}|\{\#.*?\#\})')

    def __init__(self, template_text, *contexts):
        self.template_text = template_text
        self.context = {}
        for context in contexts:
            self.context.update(context)
        self.all_vars = set()
        self.loop_vars = set()

        code = CodeBuilder()
        code.add_line('def render_function(context, do_dots):')
        code.indent()
        var_section = code.add_section()
        code.add_line('result=[]')
        code.add_line('append_result=result.append')
        code.add_line('extend_result=result.extend')
        code.add_line('to_str=str')

        buffered = []

        def flush_buffer():
            if len(buffered) == 1:
                code.add_line('append_result({})'.format(buffered[0]))
            elif len(buffered) > 1:
                code.add_line('extend_result([{}])'.format(','.join(buffered)))
            del buffered[:]

        ops_stack = []

        tokens = self.SPLIT_PATTERN.split(self.template_text)

        for token in tokens:
            if token.startswith('{#'):
                pass
            elif token.startswith('{{'):
                expr = self._expr_code(token[2:-2].strip())
                buffered.append("to_str({})".format(expr))
            elif token.startswith('{%'):
                flush_buffer()
                words = token[2:-2].strip().split()
                if words[0] == 'if':
                    if len(words) != 2:
                        self._syntax_error("Don't understand if statement", token)
                    ops_stack.append('if')
                    code.add_line('if {}'.format(self._expr_code(words[1])))
                    code.indent()
                elif words[0] == 'for':
                    if len(words) != 4 or words[2] != 'in':
                        self._syntax_error("Don't understand for statement", token)
                    ops_stack.append('for')
                    self._variable(words[1], self.loop_vars)
                    code.add_line('for c_{} in {}:'.format(words[1], self._expr_code(words[3])))
                    code.indent()
                elif words[0].startswith('end'):
                    if len(words) != 1:
                        self._syntax_error("Don't understand end", token)
                    endwhat = words[0][3:]
                    if not ops_stack:
                        self._syntax_error("Too many ends", token)
                    startwhat = ops_stack.pop()
                    if startwhat != endwhat:
                        self._syntax_error("Mismatch end tag", endwhat)
                    code.dedent()
                else:
                    self._syntax_error("Unknown tag ", token)
            else:
                if token:
                    buffered.append(repr(token))
        if ops_stack:
            self._syntax_error("Unmatched action tag", ops_stack[-1])
        flush_buffer()

        for var_name in self.all_vars - self.loop_vars:
            var_section.add_line("c_{var_name} = context['{var_name}']".format(var_name=var_name))
        code.add_line('return "".join(result)')
        code.dedent()
        self._render_function = code.get_globals()['render_function']

    def render(self, context=None):
        render_context = dict(self.context)
        if context:
            render_context.update(context)
        return self._render_function(render_context, self._do_dots)

    def _expr_code(self, expr):
        if '.' in expr:
            tokens = expr.split('.')
            code = self._expr_code(tokens[0])
            args = ', '.join(repr(d) for d in tokens[1:])
            code = 'do_dots({}, {})'.format(code, args)
        elif '|' in expr:
            pipes = expr.split("|")
            code = self._expr_code(pipes[0])
            for func in pipes[1:]:
                self._variable(func, self.all_vars)
                code = "c_%s(%s)" % (func, code)
        else:
            self._variable(expr, self.all_vars)
            code = 'c_{}'.format(expr)
        return code

    def _syntax_error(self, message, thing):
        raise TempliteException("{}: {}".format(message, thing))

    def _variable(self, variable, vars_set):
        if not re.match(r'[_a-zA-Z][_a-zA-Z0-9]*$', variable):
            self._syntax_error('Not a vali name', variable)
        vars_set.add(variable)

    def _do_dots(self, value, *dots):
        for dot in dots:
            try:
                value = getattr(value, dot)
            except AttributeError:
                value = value[dot]
            if callable(value):
                value = value()
        return value


class TempliteException(Exception):
    pass


if __name__ == '__main__':
    html = '<p>Welcome, {{user_name}}!</p>' \
           '<p>Products:</p>' \
           '<ul>' \
           '{% for product in product_list %}' \
           '<li>{{ product.name }}:' \
           '{{ product.price }}</li>' \
           '{% endfor %}' \
           '</ul>'
    template = Templite(html)
    print template.render({'user_name':'preyta',
                     'product_list': [{'name':'name1', 'price':'1 dollar'}, {'name':'name2', 'price':'2 dollar'}],})

