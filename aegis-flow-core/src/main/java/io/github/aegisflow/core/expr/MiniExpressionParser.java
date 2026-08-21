package io.github.aegisflow.core.expr;

import java.util.ArrayList;
import java.util.List;

/**
 * Recursive descent parser for AegisFlow constraint expressions.
 * Converts constraint strings into an ExprNode AST.
 */
public class MiniExpressionParser {

    private enum TokenType {
        NUMBER,
        STRING,
        BOOLEAN,
        NULL,
        IDENTIFIER,
        // Operators
        PLUS, MINUS, STAR, SLASH, PERCENT,
        EQ, NE, LT, LE, GT, GE,
        AND, OR, NOT, IMPLIES,
        // Punctuation
        LPAREN, RPAREN, COMMA,
        EOF
    }

    private static class Token {
        final TokenType type;
        final String text;
        final Object value;
        final int pos;

        Token(TokenType type, String text, Object value, int pos) {
            this.type = type;
            this.text = text;
            this.value = value;
            this.pos = pos;
        }

        @Override
        public String toString() {
            return type + "(" + text + ")";
        }
    }

    /**
     * Parses the expression string into an ExprNode AST.
     *
     * @param expression expression string
     * @return ExprNode AST, or null if expression is blank
     */
    public ExprNode parse(String expression) {
        if (expression == null || expression.trim().isEmpty()) {
            return null;
        }
        List<Token> tokens = tokenize(expression);
        ParserState state = new ParserState(tokens, expression);
        ExprNode ast = parseImplication(state);
        if (!state.isAtEnd()) {
            throw new ParseException("Unexpected token after expression: " + state.peek().text +
                    " at position " + state.peek().pos + " in: " + expression);
        }
        return ast;
    }

    // --- Lexer / Tokenizer ---

    private List<Token> tokenize(String input) {
        List<Token> tokens = new ArrayList<>();
        int i = 0;
        int len = input.length();

        while (i < len) {
            char c = input.charAt(i);

            if (Character.isWhitespace(c)) {
                i++;
                continue;
            }

            int startPos = i;

            // Two-character and Three-character operators
            if (c == '=' && i + 2 < len && input.charAt(i + 1) == '=' && input.charAt(i + 2) == '>') {
                tokens.add(new Token(TokenType.IMPLIES, "==>", null, startPos));
                i += 3;
                continue;
            }
            if (c == '=' && i + 1 < len && input.charAt(i + 1) == '=') {
                tokens.add(new Token(TokenType.EQ, "==", null, startPos));
                i += 2;
                continue;
            }
            if (c == '!' && i + 1 < len && input.charAt(i + 1) == '=') {
                tokens.add(new Token(TokenType.NE, "!=", null, startPos));
                i += 2;
                continue;
            }
            if (c == '<' && i + 1 < len && input.charAt(i + 1) == '=') {
                tokens.add(new Token(TokenType.LE, "<=", null, startPos));
                i += 2;
                continue;
            }
            if (c == '>' && i + 1 < len && input.charAt(i + 1) == '=') {
                tokens.add(new Token(TokenType.GE, ">=", null, startPos));
                i += 2;
                continue;
            }
            if (c == '&' && i + 1 < len && input.charAt(i + 1) == '&') {
                tokens.add(new Token(TokenType.AND, "&&", null, startPos));
                i += 2;
                continue;
            }
            if (c == '|' && i + 1 < len && input.charAt(i + 1) == '|') {
                tokens.add(new Token(TokenType.OR, "||", null, startPos));
                i += 2;
                continue;
            }

            // Single-character operators and symbols
            switch (c) {
                case '+': tokens.add(new Token(TokenType.PLUS, "+", null, startPos)); i++; continue;
                case '-': tokens.add(new Token(TokenType.MINUS, "-", null, startPos)); i++; continue;
                case '*': tokens.add(new Token(TokenType.STAR, "*", null, startPos)); i++; continue;
                case '/': tokens.add(new Token(TokenType.SLASH, "/", null, startPos)); i++; continue;
                case '%': tokens.add(new Token(TokenType.PERCENT, "%", null, startPos)); i++; continue;
                case '<': tokens.add(new Token(TokenType.LT, "<", null, startPos)); i++; continue;
                case '>': tokens.add(new Token(TokenType.GT, ">", null, startPos)); i++; continue;
                case '!': tokens.add(new Token(TokenType.NOT, "!", null, startPos)); i++; continue;
                case '(': tokens.add(new Token(TokenType.LPAREN, "(", null, startPos)); i++; continue;
                case ')': tokens.add(new Token(TokenType.RPAREN, ")", null, startPos)); i++; continue;
                case ',': tokens.add(new Token(TokenType.COMMA, ",", null, startPos)); i++; continue;
            }

            // String literals: 'text' or "text"
            if (c == '\'' || c == '"') {
                char quote = c;
                i++;
                StringBuilder sb = new StringBuilder();
                while (i < len && input.charAt(i) != quote) {
                    if (input.charAt(i) == '\\' && i + 1 < len) {
                        i++;
                        sb.append(input.charAt(i));
                    } else {
                        sb.append(input.charAt(i));
                    }
                    i++;
                }
                if (i >= len) {
                    throw new ParseException("Unterminated string literal starting at position " + startPos);
                }
                i++; // skip closing quote
                tokens.add(new Token(TokenType.STRING, sb.toString(), sb.toString(), startPos));
                continue;
            }

            // Number literals: integer or float
            if (Character.isDigit(c)) {
                StringBuilder sb = new StringBuilder();
                boolean isFloat = false;
                while (i < len && (Character.isDigit(input.charAt(i)) || input.charAt(i) == '.')) {
                    if (input.charAt(i) == '.') {
                        if (isFloat) break; // second dot
                        // check if next char is digit (so it's not a dot notation on number)
                        if (i + 1 < len && Character.isDigit(input.charAt(i + 1))) {
                            isFloat = true;
                        } else {
                            break;
                        }
                    }
                    sb.append(input.charAt(i));
                    i++;
                }
                String numStr = sb.toString();
                Object val = isFloat ? (Object) Double.valueOf(numStr) : (Object) Long.valueOf(numStr);
                tokens.add(new Token(TokenType.NUMBER, numStr, val, startPos));
                continue;
            }

            // Identifiers / Keywords
            if (Character.isJavaIdentifierStart(c)) {
                StringBuilder sb = new StringBuilder();
                while (i < len && (Character.isJavaIdentifierPart(input.charAt(i)) || input.charAt(i) == '.')) {
                    sb.append(input.charAt(i));
                    i++;
                }
                String id = sb.toString();
                if ("true".equalsIgnoreCase(id)) {
                    tokens.add(new Token(TokenType.BOOLEAN, id, Boolean.TRUE, startPos));
                } else if ("false".equalsIgnoreCase(id)) {
                    tokens.add(new Token(TokenType.BOOLEAN, id, Boolean.FALSE, startPos));
                } else if ("null".equalsIgnoreCase(id)) {
                    tokens.add(new Token(TokenType.NULL, id, null, startPos));
                } else if ("and".equalsIgnoreCase(id)) {
                    tokens.add(new Token(TokenType.AND, id, null, startPos));
                } else if ("or".equalsIgnoreCase(id)) {
                    tokens.add(new Token(TokenType.OR, id, null, startPos));
                } else if ("not".equalsIgnoreCase(id)) {
                    tokens.add(new Token(TokenType.NOT, id, null, startPos));
                } else {
                    tokens.add(new Token(TokenType.IDENTIFIER, id, id, startPos));
                }
                continue;
            }

            throw new ParseException("Unexpected character '" + c + "' at position " + startPos + " in: " + input);
        }

        tokens.add(new Token(TokenType.EOF, "", null, len));
        return tokens;
    }

    // --- Parser Engine ---

    private static class ParserState {
        private final List<Token> tokens;
        private final String originalInput;
        private int current = 0;

        ParserState(List<Token> tokens, String originalInput) {
            this.tokens = tokens;
            this.originalInput = originalInput;
        }

        Token peek() {
            return tokens.get(current);
        }

        Token previous() {
            return tokens.get(current - 1);
        }

        boolean isAtEnd() {
            return peek().type == TokenType.EOF;
        }

        Token advance() {
            if (!isAtEnd()) current++;
            return previous();
        }

        boolean check(TokenType type) {
            if (isAtEnd()) return false;
            return peek().type == type;
        }

        boolean match(TokenType... types) {
            for (TokenType type : types) {
                if (check(type)) {
                    advance();
                    return true;
                }
            }
            return false;
        }

        Token consume(TokenType type, String message) {
            if (check(type)) return advance();
            throw new ParseException(message + " (Found " + peek().type + " '" + peek().text +
                    "' at pos " + peek().pos + ") in: " + originalInput);
        }
    }

    // Precedence 1: Implication (==>)
    private ExprNode parseImplication(ParserState state) {
        ExprNode expr = parseLogicalOr(state);
        while (state.match(TokenType.IMPLIES)) {
            ExprNode right = parseImplication(state); // right-associative implication
            expr = new BinaryOpNode(expr, BinaryOpNode.Operator.IMPLIES, right);
        }
        return expr;
    }

    // Precedence 2: Logical OR (||)
    private ExprNode parseLogicalOr(ParserState state) {
        ExprNode expr = parseLogicalAnd(state);
        while (state.match(TokenType.OR)) {
            ExprNode right = parseLogicalAnd(state);
            expr = new BinaryOpNode(expr, BinaryOpNode.Operator.OR, right);
        }
        return expr;
    }

    // Precedence 3: Logical AND (&&)
    private ExprNode parseLogicalAnd(ParserState state) {
        ExprNode expr = parseEquality(state);
        while (state.match(TokenType.AND)) {
            ExprNode right = parseEquality(state);
            expr = new BinaryOpNode(expr, BinaryOpNode.Operator.AND, right);
        }
        return expr;
    }

    // Precedence 4: Equality (==, !=)
    private ExprNode parseEquality(ParserState state) {
        ExprNode expr = parseRelational(state);
        while (state.match(TokenType.EQ, TokenType.NE)) {
            TokenType type = state.previous().type;
            BinaryOpNode.Operator op = (type == TokenType.EQ) ? BinaryOpNode.Operator.EQ : BinaryOpNode.Operator.NE;
            ExprNode right = parseRelational(state);
            expr = new BinaryOpNode(expr, op, right);
        }
        return expr;
    }

    // Precedence 5: Relational (<, <=, >, >=)
    private ExprNode parseRelational(ParserState state) {
        ExprNode expr = parseAdditive(state);
        while (state.match(TokenType.LT, TokenType.LE, TokenType.GT, TokenType.GE)) {
            TokenType type = state.previous().type;
            BinaryOpNode.Operator op = switch (type) {
                case LT -> BinaryOpNode.Operator.LT;
                case LE -> BinaryOpNode.Operator.LE;
                case GT -> BinaryOpNode.Operator.GT;
                case GE -> BinaryOpNode.Operator.GE;
                default -> throw new IllegalStateException();
            };
            ExprNode right = parseAdditive(state);
            expr = new BinaryOpNode(expr, op, right);
        }
        return expr;
    }

    // Precedence 6: Additive (+, -)
    private ExprNode parseAdditive(ParserState state) {
        ExprNode expr = parseMultiplicative(state);
        while (state.match(TokenType.PLUS, TokenType.MINUS)) {
            TokenType type = state.previous().type;
            BinaryOpNode.Operator op = (type == TokenType.PLUS) ? BinaryOpNode.Operator.ADD : BinaryOpNode.Operator.SUB;
            ExprNode right = parseMultiplicative(state);
            expr = new BinaryOpNode(expr, op, right);
        }
        return expr;
    }

    // Precedence 7: Multiplicative (*, /, %)
    private ExprNode parseMultiplicative(ParserState state) {
        ExprNode expr = parseUnary(state);
        while (state.match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT)) {
            TokenType type = state.previous().type;
            BinaryOpNode.Operator op = switch (type) {
                case STAR -> BinaryOpNode.Operator.MUL;
                case SLASH -> BinaryOpNode.Operator.DIV;
                case PERCENT -> BinaryOpNode.Operator.MOD;
                default -> throw new IllegalStateException();
            };
            ExprNode right = parseUnary(state);
            expr = new BinaryOpNode(expr, op, right);
        }
        return expr;
    }

    // Precedence 8: Unary (!, -, +)
    private ExprNode parseUnary(ParserState state) {
        if (state.match(TokenType.NOT)) {
            ExprNode operand = parseUnary(state);
            return new UnaryOpNode(UnaryOpNode.Operator.NOT, operand);
        }
        if (state.match(TokenType.MINUS)) {
            ExprNode operand = parseUnary(state);
            return new UnaryOpNode(UnaryOpNode.Operator.NEG, operand);
        }
        if (state.match(TokenType.PLUS)) {
            return parseUnary(state); // unary plus is a no-op
        }
        return parsePrimary(state);
    }

    // Precedence 9: Primary (literals, identifiers, function calls, groupings)
    private ExprNode parsePrimary(ParserState state) {
        if (state.match(TokenType.BOOLEAN, TokenType.NUMBER, TokenType.STRING, TokenType.NULL)) {
            return new LiteralNode(state.previous().value);
        }

        if (state.match(TokenType.IDENTIFIER)) {
            String name = state.previous().text;
            // Check for function call: identifier '(' ... ')'
            if (state.match(TokenType.LPAREN)) {
                List<ExprNode> args = new ArrayList<>();
                if (!state.check(TokenType.RPAREN)) {
                    do {
                        args.add(parseImplication(state));
                    } while (state.match(TokenType.COMMA));
                }
                state.consume(TokenType.RPAREN, "Expected ')' after function arguments");
                return new FunctionCallNode(name, args);
            }
            return new IdentifierNode(name);
        }

        if (state.match(TokenType.LPAREN)) {
            ExprNode expr = parseImplication(state);
            state.consume(TokenType.RPAREN, "Expected ')' after expression");
            return expr;
        }

        throw new ParseException("Expected expression at position " + state.peek().pos +
                ", found: " + state.peek().text + " in: " + state.originalInput);
    }
}
