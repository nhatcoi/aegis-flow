package io.github.aegisflow.core.expr;

/**
 * Visitor interface for traversing Expression AST nodes.
 */
public interface ExprVisitor<T> {

    T visitBinary(BinaryOpNode node);

    T visitUnary(UnaryOpNode node);

    T visitIdentifier(IdentifierNode node);

    T visitLiteral(LiteralNode node);

    T visitFunctionCall(FunctionCallNode node);
}
