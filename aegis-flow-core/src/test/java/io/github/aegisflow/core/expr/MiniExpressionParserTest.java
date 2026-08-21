package io.github.aegisflow.core.expr;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class MiniExpressionParserTest {

    private MiniExpressionParser parser;

    @BeforeEach
    void setUp() {
        parser = new MiniExpressionParser();
    }

    @Test
    void testParseLiterals() {
        ExprNode num = parser.parse("42");
        assertThat(num).isInstanceOf(LiteralNode.class);
        assertThat(num.evaluate(Map.of())).isEqualTo(42L);

        ExprNode str = parser.parse("'hello world'");
        assertThat(str.evaluate(Map.of())).isEqualTo("hello world");

        ExprNode bool = parser.parse("true");
        assertThat(bool.evaluate(Map.of())).isEqualTo(true);

        ExprNode nil = parser.parse("null");
        assertThat(nil.evaluate(Map.of())).isNull();
    }

    @Test
    void testParseIdentifiersAndPropertyAccess() {
        ExprNode expr = parser.parse("balance");
        assertThat(expr).isInstanceOf(IdentifierNode.class);
        assertThat(expr.evaluate(Map.of("balance", 1000L))).isEqualTo(1000L);

        ExprNode dotExpr = parser.parse("order.status");
        assertThat(dotExpr.evaluate(Map.of("order", Map.of("status", "PAID")))).isEqualTo("PAID");
    }

    @Test
    void testArithmeticOperatorsAndPrecedence() {
        ExprNode expr = parser.parse("10 + 2 * 5 - 4 / 2");
        // 10 + (2 * 5) - (4 / 2) = 10 + 10 - 2 = 18
        assertThat(expr.evaluate(Map.of())).isEqualTo(18L);

        ExprNode parenExpr = parser.parse("(10 + 2) * (5 - 3)");
        assertThat(parenExpr.evaluate(Map.of())).isEqualTo(24L);
    }

    @Test
    void testComparisonAndLogicalOperators() {
        ExprNode expr = parser.parse("amount > 0 && amount <= balance");
        Map<String, Object> ctxValid = Map.of("amount", 50L, "balance", 100L);
        assertThat(expr.evaluate(ctxValid)).isEqualTo(true);

        Map<String, Object> ctxInvalid = Map.of("amount", 150L, "balance", 100L);
        assertThat(expr.evaluate(ctxInvalid)).isEqualTo(false);
    }

    @Test
    void testLogicalImplication() {
        // A ==> B is equivalent to !A || B
        ExprNode impl = parser.parse("isDelivered ==> !isCancelled");

        // True ==> True -> True
        assertThat(impl.evaluate(Map.of("isDelivered", true, "isCancelled", false))).isEqualTo(true);

        // True ==> False -> False
        assertThat(impl.evaluate(Map.of("isDelivered", true, "isCancelled", true))).isEqualTo(false);

        // False ==> Anything -> True
        assertThat(impl.evaluate(Map.of("isDelivered", false, "isCancelled", true))).isEqualTo(true);
    }

    @Test
    void testUnaryOperators() {
        ExprNode notExpr = parser.parse("!(amount <= 0)");
        assertThat(notExpr.evaluate(Map.of("amount", 10L))).isEqualTo(true);
        assertThat(notExpr.evaluate(Map.of("amount", -5L))).isEqualTo(false);

        ExprNode negExpr = parser.parse("-x + 10");
        assertThat(negExpr.evaluate(Map.of("x", 4L))).isEqualTo(6L);
    }

    @Test
    void testFunctionCalls() {
        ExprNode oldFunc = parser.parse("balance == old(balance) - amount");
        Map<String, Object> ctx = Map.of(
                "balance", 70L,
                "old_balance", 100L,
                "amount", 30L
        );
        assertThat(oldFunc.evaluate(ctx)).isEqualTo(true);

        ExprNode absFunc = parser.parse("abs(-42)");
        assertThat(absFunc.evaluate(Map.of())).isEqualTo(42.0);
    }

    @Test
    void testParseErrors() {
        assertThatThrownBy(() -> parser.parse("amount > "))
                .isInstanceOf(ParseException.class);

        assertThatThrownBy(() -> parser.parse("(balance + 10"))
                .isInstanceOf(ParseException.class);
    }
}
